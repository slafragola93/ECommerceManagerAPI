"""
Interfaccia per OrderState Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.order_state_schema import OrderStateSchema, OrderStateResponseSchema
from src.models.order_state import OrderState

class IOrderStateService(IBaseService):
    """Interface per il servizio order_state"""
    
    @abstractmethod
    async def create_order_state(self, order_state_data: OrderStateSchema) -> OrderState:
        """Crea un nuovo order_state"""
        pass
    
    @abstractmethod
    async def update_order_state(self, order_state_id: int, order_state_data: OrderStateSchema) -> OrderState:
        """Aggiorna un order_state esistente"""
        pass
    
    @abstractmethod
    async def get_order_state(self, order_state_id: int) -> OrderState:
        """Ottiene un order_state per ID"""
        pass
    
    @abstractmethod
    async def get_order_states(self, page: int = 1, limit: int = 10, **filters) -> List[OrderState]:
        """Ottiene la lista dei order_state con filtri"""
        pass
    
    @abstractmethod
    async def delete_order_state(self, order_state_id: int) -> bool:
        """Elimina un order_state"""
        pass
    
    @abstractmethod
    async def get_order_states_count(self, **filters) -> int:
        """Ottiene il numero totale di order_state con filtri"""
        pass
