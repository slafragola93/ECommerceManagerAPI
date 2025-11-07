"""
Product Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any

from sqlalchemy.orm import Session

from src.services.interfaces.product_service_interface import IProductService
from src.repository.interfaces.product_repository_interface import IProductRepository
from src.repository.interfaces.platform_repository_interface import IPlatformRepository
from src.schemas.product_schema import ProductSchema
from src.models.product import Product
from src.services.ecommerce.service_factory import create_ecommerce_service
from src.core.exceptions import (
    ValidationException,
    NotFoundException,
    BusinessRuleException,
    InfrastructureException,
    ErrorCode,
)
from src.events.decorators import emit_event_on_success
from src.events.core.event import EventType
from src.events.extractors import (
    extract_product_created_data,
    extract_product_updated_data
)


class ProductService(IProductService):
    """Product Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""

    def __init__(self, product_repository: IProductRepository):
        self._product_repository = product_repository
        self._platform_repository: Optional[IPlatformRepository] = None
        self._db: Optional[Session] = None

    def set_dependencies(
        self,
        product_repository: IProductRepository,
        platform_repository: IPlatformRepository,
        db: Session,
    ) -> None:
        self._product_repository = product_repository
        self._platform_repository = platform_repository
        self._db = db
    
    @emit_event_on_success(
        event_type=EventType.PRODUCT_CREATED,
        data_extractor=extract_product_created_data,
        source="product_service.create_product"
    )
    async def create_product(self, product_data: ProductSchema, user: dict = None) -> Product:
        """
        Crea un nuovo product con validazioni business.
        
        Args:
            product_data: Dati del prodotto da creare
            user: Contesto utente per eventi (tenant, user_id)
        
        Returns:
            Product creato
        """
        
        # Business Rule 1: Nome deve essere unico
        if hasattr(product_data, 'name') and product_data.name:
            existing_product = self._product_repository.get_by_name(product_data.name)
            if existing_product:
                raise BusinessRuleException(
                    f"Prodotto con nome '{product_data.name}' già esistente",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": product_data.name}
                )
        
        # Crea il product
        try:
            product = Product(**product_data.model_dump())
            product = self._product_repository.create(product)
            return product
        except Exception as e:
            raise ValidationException(f"Errore nella creazione del prodotto: {str(e)}")
    
    @emit_event_on_success(
        event_type=EventType.PRODUCT_UPDATED,
        data_extractor=extract_product_updated_data,
        source="product_service.update_product"
    )
    async def update_product(self, product_id: int, product_data: ProductSchema, user: dict = None) -> Product:
        """
        Aggiorna un product esistente.
        
        Args:
            product_id: ID del prodotto da aggiornare
            product_data: Nuovi dati del prodotto
            user: Contesto utente per eventi (tenant, user_id)
        
        Returns:
            Product aggiornato
        """
        
        # Verifica esistenza
        product = self._product_repository.get_by_id_or_raise(product_id)
        
        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(product_data, 'name') and product_data.name != product.name:
            existing = self._product_repository.get_by_name(product_data.name)
            if existing and existing.id_product != product_id:
                raise BusinessRuleException(
                    f"Prodotto con nome '{product_data.name}' già esistente",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": product_data.name}
                )
        
        # Aggiorna il product
        try:
            updated_product = self._product_repository.update(product, product_data)
            return updated_product
        except Exception as e:
            raise ValidationException(f"Errore nell'aggiornamento del prodotto: {str(e)}")
    
    async def get_product(self, product_id: int) -> Product:
        """Ottiene un product per ID"""
        product = self._product_repository.get_by_id_or_raise(product_id)
        return product
    
    async def get_products(self, page: int = 1, limit: int = 10, **filters) -> List[Product]:
        """Ottiene la lista dei product con filtri"""
        try:
            # Validazione parametri
            if page < 1:
                page = 1
            if limit < 1:
                limit = 10
            
            # Aggiungi page e limit ai filtri
            filters['page'] = page
            filters['limit'] = limit
            
            # Usa il repository con i filtri
            products = self._product_repository.get_all(**filters)
            
            return products
        except Exception as e:
            raise ValidationException(f"Errore nel recupero dei prodotti: {str(e)}")
    

    async def delete_product(self, product_id: int, user: dict = None) -> bool:
        """
        Elimina un product.
        
        Args:
            product_id: ID del prodotto da eliminare
            user: Contesto utente per eventi (tenant, user_id)
        
        Returns:
            True se eliminato con successo
        """
        # Verifica esistenza e ottieni il prodotto
        product = self._product_repository.get_by_id_or_raise(product_id)
        
        try:
            return self._product_repository.delete(product)
        except Exception as e:
            raise ValidationException(f"Errore nell'eliminazione del prodotto: {str(e)}")
    
    async def get_products_count(self, **filters) -> int:
        """Ottiene il numero totale di product con filtri"""
        try:
            # Usa il repository con i filtri
            return self._product_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Errore nel conteggio dei prodotti: {str(e)}")
    
    async def get_live_price(self, id_origin: int) -> Optional[float]:
        self._ensure_dependencies_configured()

        product = self._product_repository.get_by_origin_id(str(id_origin))
        if not product:
            raise NotFoundException(
                "Product",
                None,
                {"id_origin": id_origin},
            )

        if not product.id_platform:
            raise BusinessRuleException(
                "Product has no platform associated",
                details={"id_origin": id_origin},
            )

        platform = self._platform_repository.get_by_id(product.id_platform)
        if not platform:
            raise NotFoundException(
                "Platform",
                product.id_platform,
                {"id_origin": id_origin},
            )

        ecommerce_service = create_ecommerce_service(platform, self._db)

        try:
            async with ecommerce_service as service:
                return await service.get_live_price(id_origin)
        except (InfrastructureException, BusinessRuleException, NotFoundException):
            raise
        except Exception as exc:
            raise InfrastructureException(
                "Errore nel recupero del prezzo live",
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                {
                    "id_origin": id_origin,
                    "platform_id": platform.id_platform,
                    "platform_name": platform.name,
                },
            ) from exc

    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Product"""
        # Validazioni specifiche per Product se necessarie
        pass

    def _ensure_dependencies_configured(self) -> None:
        if not self._product_repository or not self._platform_repository or not self._db:
            raise RuntimeError("ProductService dependencies are not configured")
