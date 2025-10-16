"""
Interfaccia per Address Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.address import Address

class IAddressRepository(IRepository[Address, int]):
    """Interface per la repository dei address"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Address]:
        """Ottiene un address per nome"""
        pass
