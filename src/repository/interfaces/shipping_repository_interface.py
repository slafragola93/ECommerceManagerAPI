"""
Interfaccia per Shipping Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.shipping import Shipping

class IShippingRepository(IRepository[Shipping, int]):
    """Interface per la repository dei shipping"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Shipping]:
        """Ottiene un shipping per nome"""
        pass
