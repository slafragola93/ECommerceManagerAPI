"""
Interfaccia per Order Service seguendo ISP (Interface Segregation Principle)
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from src.core.interfaces import IBaseService
from src.schemas.order_schema import (
    OrderSchema,
    OrderUpdateSchema,
    OrderIdSchema,
    OrderStatusUpdateItem,
    BulkOrderStatusUpdateResponseSchema
)


class IOrderService(IBaseService):
    """Interface per il servizio order"""
    
    @abstractmethod
    async def update_order_status(
        self, 
        order_id: int,
        new_status_id: int
    ) -> Dict[str, Any]:
        """
        Aggiorna lo stato di un ordine e crea record in orders_history.
        
        Args:
            order_id: ID dell'ordine
            new_status_id: Nuovo stato dell'ordine
            
        Returns:
            Dict con message, order_id, new_status_id, old_state_id
        """
        pass
    
    @abstractmethod
    async def update_order(
        self,
        order_id: int,
        order_schema: OrderUpdateSchema
    ) -> Dict[str, Any]:
        """
        Aggiorna un ordine esistente.
        
        Args:
            order_id: ID dell'ordine
            order_schema: Schema con i campi da aggiornare
            
        Returns:
            Dict con message, order_id, e opzionalmente old_state_id, new_state_id
        """
        pass
    
    @abstractmethod
    async def bulk_update_order_status(
        self, 
        updates: List[OrderStatusUpdateItem]
    ) -> BulkOrderStatusUpdateResponseSchema:
        """
        Aggiorna gli stati di più ordini in modo massivo.
        
        Args:
            updates: Lista di aggiornamenti stato ordine
            
        Returns:
            Risposta con successi, fallimenti e summary
        """
        pass
