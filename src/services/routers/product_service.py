"""
Product Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any, Dict

from sqlalchemy.orm import Session

from src.services.interfaces.product_service_interface import IProductService
from src.repository.interfaces.product_repository_interface import IProductRepository
from src.repository.interfaces.platform_repository_interface import IPlatformRepository
from src.repository.tax_repository import TaxRepository
from src.schemas.product_schema import ProductSchema
from src.schemas.category_schema import CategoryResponseSchema
from src.schemas.brand_schema import BrandResponseSchema
from src.models.product import Product
from src.services.ecommerce.service_factory import create_ecommerce_service
from src.services.core.tool import calculate_price_without_tax, calculate_price_with_tax
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
            user: Contesto utente per eventi (user_id)
        
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
            user: Contesto utente per eventi (user_id)
        
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
    
    def _enrich_product_with_tax_info(self, product: Product, id_country: Optional[int], db: Session) -> dict:
        """
        Arricchisce un prodotto con informazioni IVA (price_with_tax, price_net, id_tax).
        
        Args:
            product: Prodotto da arricchire
            id_country: ID del paese (opzionale) per calcolare IVA
            db: Database session per accedere a TaxRepository
        
        Returns:
            dict con i dati del prodotto arricchiti
        """
        # Prepara i dati base del prodotto
        # Converti category e brand in dict se presenti
        category_dict = None
        if product.category is not None:
            category_schema = CategoryResponseSchema.model_validate(product.category)
            category_dict = category_schema.model_dump()
        
        brand_dict = None
        if product.brand is not None:
            brand_schema = BrandResponseSchema.model_validate(product.brand)
            brand_dict = brand_schema.model_dump()
        
        product_dict = {
            "id_product": product.id_product,
            "id_origin": product.id_origin,
            "id_platform": product.id_platform,
            "img_url": product.img_url,
            "name": product.name,
            "sku": product.sku,
            "reference": product.reference,
            "type": product.type,
            "weight": float(product.weight) if product.weight is not None else 0.0,
            "depth": float(product.depth) if product.depth is not None else 0.0,
            "height": float(product.height) if product.height is not None else 0.0,
            "width": float(product.width) if product.width is not None else 0.0,
            "price_with_tax": float(product.price) if product.price is not None else None,
            "quantity": product.quantity,
            "purchase_price": float(product.purchase_price) if product.purchase_price is not None else None,
            "minimal_quantity": product.minimal_quantity,
            "category": category_dict,
            "brand": brand_dict,
        }
        
        # Se id_country è fornito, calcola price_net e id_tax
        if id_country is not None:
            tax_repo = TaxRepository(db)
            tax_info = tax_repo.get_tax_info_by_country(id_country)
            
            if tax_info and product.price is not None:
                tax_percentage = tax_info.get("percentage", 22.0)
                product_dict["price_net"] = calculate_price_without_tax(    
                    float(product.price),
                    tax_percentage
                )
                product_dict["id_tax"] = tax_info.get("id_tax")
            else:
                product_dict["price_net"] = None
                product_dict["id_tax"] = None
        else:
            product_dict["price_net"] = None
            product_dict["id_tax"] = None
        
        return product_dict
    
    async def get_product(self, product_id: int, id_country: Optional[int] = None) -> dict:
        """
        Ottiene un product per ID con informazioni IVA opzionali.
        
        Args:
            product_id: ID del prodotto
            id_country: ID del paese (opzionale) per calcolare IVA
        
        Returns:
            dict con i dati del prodotto arricchiti
        """
        self._ensure_dependencies_configured()
        product = self._product_repository.get_by_id_or_raise(product_id)
        
        return self._enrich_product_with_tax_info(product, id_country, self._db)
    
    async def get_products(self, page: int = 1, limit: int = 10, id_country: Optional[int] = None, **filters) -> List[dict]:
        """
        Ottiene la lista dei product con filtri e informazioni IVA opzionali.
        
        Args:
            page: Numero di pagina
            limit: Limite di risultati per pagina
            id_country: ID del paese (opzionale) per calcolare IVA
            **filters: Filtri aggiuntivi
        
        Returns:
            Lista di dict con i dati dei prodotti arricchiti
        """
        try:
            self._ensure_dependencies_configured()
            
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
            
            # Arricchisci ogni prodotto con informazioni IVA
            enriched_products = [
                self._enrich_product_with_tax_info(product, id_country, self._db)
                for product in products
            ]
            
            return enriched_products
        except Exception as e:
            raise ValidationException(f"Errore nel recupero dei prodotti: {str(e)}")
    

    async def delete_product(self, product_id: int, user: dict = None) -> bool:
        """
        Elimina un product.
        
        Args:
            product_id: ID del prodotto da eliminare
            user: Contesto utente per eventi (user_id)
        
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
    
    def get_product_images_map(self, product_ids: List[int]) -> Dict[int, str]:
        """
        Recupera img_url per una lista di product_ids in batch (performance optimization).
        Segue SRP: responsabilità singola del Product Service di gestire tutto ciò che riguarda i prodotti.
        
        Args:
            product_ids: Lista di ID prodotti
            
        Returns:
            Dictionary {id_product: img_url}, con fallback se img_url è None
        """
        return self._product_repository.get_products_images_map(product_ids)
    
    async def get_live_price(self, id_origin: int) -> Optional[float]:
        """
        Recupera il prezzo live di un prodotto dall'ecommerce e lo restituisce con IVA applicata.
        
        Args:
            id_origin: ID origin del prodotto nell'ecommerce
        
        Returns:
            Prezzo con IVA applicata usando la percentuale di default da app_configuration
        """
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
                # Recupera il prezzo senza IVA dall'ecommerce
                price_without_tax = await service.get_live_price(id_origin)
                
                if price_without_tax is None or price_without_tax <= 0:
                    return price_without_tax
                
                # Recupera la percentuale IVA di default da app_configuration
                tax_repo = TaxRepository(self._db)
                default_tax_percentage = tax_repo.get_default_tax_percentage_from_app_config(22.0)
                
                # Calcola il prezzo con IVA
                price_with_tax = calculate_price_with_tax(price_without_tax, default_tax_percentage, quantity=1)
                
                return price_with_tax
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
