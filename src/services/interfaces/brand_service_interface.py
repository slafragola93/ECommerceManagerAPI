"""
Interfaccia per Brand Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.brand_schema import BrandSchema, BrandResponseSchema
from src.models.brand import Brand

class IBrandService(IBaseService):
    """Interface per il servizio brand"""
    
    @abstractmethod
    async def create_brand(self, brand_data: BrandSchema) -> Brand:
        """Crea un nuovo brand"""
        pass
    
    @abstractmethod
    async def update_brand(self, brand_id: int, brand_data: BrandSchema) -> Brand:
        """Aggiorna un brand esistente"""
        pass
    
    @abstractmethod
    async def get_brand(self, brand_id: int) -> Brand:
        """Ottiene un brand per ID"""
        pass
    
    @abstractmethod
    async def get_brands(self, page: int = 1, limit: int = 10, **filters) -> List[Brand]:
        """Ottiene la lista dei brand con filtri"""
        pass
    
    @abstractmethod
    async def delete_brand(self, brand_id: int) -> bool:
        """Elimina un brand"""
        pass
    
    @abstractmethod
    async def get_brands_count(self, **filters) -> int:
        """Ottiene il numero totale di brand con filtri"""
        pass
