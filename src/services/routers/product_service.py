"""
Product Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.product_service_interface import IProductService
from src.repository.interfaces.product_repository_interface import IProductRepository
from src.schemas.product_schema import ProductSchema
from src.models.product import Product
from src.core.exceptions import (
    ValidationException, 
    NotFoundException, 
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)

class ProductService(IProductService):
    """Product Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""
    
    def __init__(self, product_repository: IProductRepository):
        self._product_repository = product_repository
    
    async def create_product(self, product_data: ProductSchema) -> Product:
        """Crea un nuovo product con validazioni business"""
        
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
    
    async def update_product(self, product_id: int, product_data: ProductSchema) -> Product:
        """Aggiorna un product esistente"""
        
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
    
    async def delete_product(self, product_id: int) -> bool:
        """Elimina un product"""
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
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Product"""
        # Validazioni specifiche per Product se necessarie
        pass
