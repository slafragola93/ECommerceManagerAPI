"""
Interfaccia per OrderPackage Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from sqlalchemy.engine import Row
from src.core.interfaces import IRepository
from src.models.order_package import OrderPackage

class IOrderPackageRepository(IRepository[OrderPackage, int]):
    """Interface per la repository dei order_package"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[OrderPackage]:
        """Ottiene un order_package per nome"""
        pass
    
    @abstractmethod
    def get_dimensions_by_order(self, id_order: int) -> list[Row]:
        """Get package dimensions/weight for order"""
        pass
