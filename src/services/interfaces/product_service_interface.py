"""
Interfaccia per Product Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from src.core.interfaces import IBaseService
from src.schemas.product_schema import ProductSchema, ProductResponseSchema
from src.models.product import Product

class IProductService(IBaseService):
    """Interface per il servizio product"""
    
    @abstractmethod
    async def create_product(self, product_data: ProductSchema) -> Product:
        """Crea un nuovo product"""
        pass
    
    @abstractmethod
    async def update_product(self, product_id: int, product_data: ProductSchema) -> Product:
        """Aggiorna un product esistente"""
        pass
    
    @abstractmethod
    async def get_product(self, product_id: int) -> Product:
        """Ottiene un product per ID"""
        pass
    
    @abstractmethod
    async def get_products(self, page: int = 1, limit: int = 10, **filters) -> List[Product]:
        """Ottiene la lista dei product con filtri"""
        pass
    
    @abstractmethod
    async def delete_product(self, product_id: int) -> bool:
        """Elimina un product"""
        pass
    
    @abstractmethod
    async def get_products_count(self, **filters) -> int:
        """Ottiene il numero totale di product con filtri"""
        pass

    @abstractmethod
    async def get_live_price(self, id_origin: int) -> Optional[float]:
        """Recupera il prezzo live da piattaforma esterna"""
        pass
