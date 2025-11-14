"""
Stock Auto-Update Event Handlers

Handles ORDER_CREATED events to automatically decrement product stock.
Uses optimized SQL queries - only updates necessary fields.
"""
from __future__ import annotations

from src.events.core.event import Event, EventType
from src.events.interfaces import BaseEventHandler
from src.database import get_db
from sqlalchemy import text


class StockAutoUpdateHandler(BaseEventHandler):
    """Handler that automatically decrements product stock when orders are created."""
    
    def __init__(self, *, name: str = "stock_auto_update_handler") -> None:
        super().__init__(name=name)
    
    def can_handle(self, event: Event) -> bool:
        """Check if this handler can handle the event."""
        return event.event_type == EventType.ORDER_CREATED.value
    
    async def handle(self, event: Event) -> None:
        """Handle ORDER_CREATED event by decrementing product stock."""
        await self._decrement_stock(event)
    
    async def _decrement_stock(self, event: Event) -> None:
        """
        Decrementa stock prodotti quando ordine viene creato.
        
        Query ottimizzata: UPDATE SQL diretto senza SELECT preventivo.
        
        Args:
            event: Event ORDER_CREATED con order_details
        """
        # Get order details from event data
        order_details = event.data.get('order_details', [])
        
        # Fallback: se order_details non in event, fetch con query ottimizzata
        if not order_details:
            id_order = event.data.get('id_order')
            if not id_order:
                return
            
            db = next(get_db())
            try:
                # Query SQL ottimizzata: SOLO id_product e product_qty
                stmt = text(
                    "SELECT id_product, product_qty FROM order_details WHERE id_order = :id_order"
                )
                result = db.execute(stmt, {"id_order": id_order})
                order_details = [
                    {'id_product': row.id_product, 'product_qty': row.product_qty}
                    for row in result
                ]
            finally:
                db.close()
        
        if not order_details:
            return
        
        # Update stock con query SQL diretta (zero ORM object loading)
        db = next(get_db())
        try:
            # UPDATE diretto: decrementa quantity
            update_stmt = text(
                "UPDATE products SET quantity = quantity - :qty "
                "WHERE id_product = :id_product AND quantity IS NOT NULL"
            )
            
            for detail in order_details:
                id_product = detail.get('id_product')
                qty = detail.get('product_qty', 0)
                
                if id_product and qty > 0:
                    db.execute(update_stmt, {
                        'id_product': id_product,
                        'qty': qty
                    })
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            # Non rethrow - plugin non deve bloccare flusso principale
            print(f"ERROR: Stock update failed for order {event.data.get('id_order')}: {str(e)}")
            
        finally:
            db.close()


