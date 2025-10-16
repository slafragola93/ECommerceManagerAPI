"""
Interfaccia per ShippingState Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.shipping_state_schema import ShippingStateSchema, ShippingStateResponseSchema
from src.models.shipping_state import ShippingState

class IShippingStateService(IBaseService):
    """Interface per il servizio shipping_state"""
    
    @abstractmethod
    async def create_shipping_state(self, shipping_state_data: ShippingStateSchema) -> ShippingState:
        """Crea un nuovo shipping_state"""
        pass
    
    @abstractmethod
    async def update_shipping_state(self, shipping_state_id: int, shipping_state_data: ShippingStateSchema) -> ShippingState:
        """Aggiorna un shipping_state esistente"""
        pass
    
    @abstractmethod
    async def get_shipping_state(self, shipping_state_id: int) -> ShippingState:
        """Ottiene un shipping_state per ID"""
        pass
    
    @abstractmethod
    async def get_shipping_states(self, page: int = 1, limit: int = 10, **filters) -> List[ShippingState]:
        """Ottiene la lista dei shipping_state con filtri"""
        pass
    
    @abstractmethod
    async def delete_shipping_state(self, shipping_state_id: int) -> bool:
        """Elimina un shipping_state"""
        pass
    
    @abstractmethod
    async def get_shipping_states_count(self, **filters) -> int:
        """Ottiene il numero totale di shipping_state con filtri"""
        pass
