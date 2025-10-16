"""
Interfaccia per Category Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.category_schema import CategorySchema, CategoryResponseSchema
from src.models.category import Category

class ICategoryService(IBaseService):
    """Interface per il servizio category"""
    
    @abstractmethod
    async def create_category(self, category_data: CategorySchema) -> Category:
        """Crea un nuovo category"""
        pass
    
    @abstractmethod
    async def update_category(self, category_id: int, category_data: CategorySchema) -> Category:
        """Aggiorna un category esistente"""
        pass
    
    @abstractmethod
    async def get_category(self, category_id: int) -> Category:
        """Ottiene un category per ID"""
        pass
    
    @abstractmethod
    async def get_categories(self, page: int = 1, limit: int = 10, **filters) -> List[Category]:
        """Ottiene la lista dei category con filtri"""
        pass
    
    @abstractmethod
    async def delete_category(self, category_id: int) -> bool:
        """Elimina un category"""
        pass
    
    @abstractmethod
    async def get_categories_count(self, **filters) -> int:
        """Ottiene il numero totale di category con filtri"""
        pass
