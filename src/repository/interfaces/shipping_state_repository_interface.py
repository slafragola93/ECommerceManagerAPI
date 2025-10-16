"""
Interfaccia per ShippingState Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.shipping_state import ShippingState

class IShippingStateRepository(IRepository[ShippingState, int]):
    """Interface per la repository dei shipping_state"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[ShippingState]:
        """Ottiene un shipping_state per nome"""
        pass
