"""
Interfaccia per OrderState Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.order_state import OrderState

class IOrderStateRepository(IRepository[OrderState, int]):
    """Interface per la repository dei order_state"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[OrderState]:
        """Ottiene un order_state per nome"""
        pass
