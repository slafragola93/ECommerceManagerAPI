"""
Interfaccia per Category Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.category import Category

class ICategoryRepository(IRepository[Category, int]):
    """Interface per la repository dei category"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Category]:
        """Ottiene un category per nome"""
        pass
    
    @abstractmethod
    def get_by_origin_id(self, origin_id: str) -> Optional[Category]:
        """Ottiene una categoria per origin ID"""
        pass