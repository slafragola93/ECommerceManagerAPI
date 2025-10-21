"""
Interfaccia per Product Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.product import Product

class IProductRepository(IRepository[Product, int]):
    """Interface per la repository dei product"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Product]:
        """Ottiene un product per nome"""
        pass
    
    @abstractmethod
    def get_by_origin_id(self, origin_id: str) -> Optional[Product]:
        """Ottiene un prodotto per origin ID"""
        pass
    
    @abstractmethod
    def bulk_create(self, data_list: list, batch_size: int = 1000) -> int:
        """Bulk insert products for better performance"""
        pass