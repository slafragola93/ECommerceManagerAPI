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
    BulkOrderStatusUpdateResponseSchema,
    OrderStateSyncResponseSchema
)


class IOrderService(IBaseService):
    """Interface per il servizio order"""
    
    @abstractmethod
    async def create_order(self, order_data, user: dict = None):
        """Crea un nuovo ordine ed emette evento ORDER_CREATED"""
        pass
    
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

    @abstractmethod
    def recalculate_totals_for_order(self, order_id: int) -> None:
        """Ricalcola e persiste i totali di un ordine (imponibile e ivato)."""
        pass
    
    @abstractmethod
    async def sync_order_state_to_ecommerce(
        self,
        order_id: int,
        id_ecommerce_order_state: int
    ) -> OrderStateSyncResponseSchema:
        """
        Sincronizza lo stato di un ordine con la piattaforma ecommerce remota.
        
        Args:
            order_id: ID dell'ordine da sincronizzare
            id_ecommerce_order_state: ID stato ecommerce locale (PK di ecommerce_order_states)
            
        Returns:
            OrderStateSyncResponseSchema con risultato della sincronizzazione
            
        Raises:
            NotFoundException: Se ordine non trovato o EcommerceOrderState non trovato
            BusinessRuleException: Se ordine senza id_store o id_platform == 0
        """
        pass