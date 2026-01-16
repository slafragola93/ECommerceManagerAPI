"""
Platform State Sync Event Handlers

Gestisce ORDER_STATUS_CHANGED e SHIPPING_STATUS_CHANGED per sincronizzare stati con piattaforme.
"""
from __future__ import annotations

import logging
from src.events.core.event import Event, EventType
from src.events.interfaces import BaseEventHandler
from src.database import get_db
from src.repository.platform_state_trigger_repository import PlatformStateTriggerRepository

logger = logging.getLogger(__name__)


class PlatformStateSyncHandler(BaseEventHandler):
    """Handler che sincronizza stati ordini/spedizioni con piattaforme ecommerce."""
    
    def __init__(self, *, name: str = "platform_state_sync_handler") -> None:
        super().__init__(name=name)
    
    def can_handle(self, event: Event) -> bool:
        """Check if this handler can handle the event."""
        return event.event_type in [
            EventType.ORDER_STATUS_CHANGED.value,
            EventType.SHIPPING_STATUS_CHANGED.value
        ]
    
    async def handle(self, event: Event) -> None:
        """Handle ORDER_STATUS_CHANGED o SHIPPING_STATUS_CHANGED event."""
        try:
            if event.event_type == EventType.ORDER_STATUS_CHANGED.value:
                await self._sync_order_state(event)
            elif event.event_type == EventType.SHIPPING_STATUS_CHANGED.value:
                await self._sync_shipping_state(event)
        except Exception as e:
            logger.error(f"Errore in PlatformStateSyncHandler.handle: {str(e)}", exc_info=True)
            raise
    
    async def _sync_order_state(self, event: Event) -> None:
        """
        Sincronizza stato ordine con piattaforma.
        
        Args:
            event: Event ORDER_STATUS_CHANGED con order_id, old_state_id, new_state_id
        """
        try:
            order_id = event.data.get('order_id')
            new_state_id = event.data.get('new_state_id')
            
            if not order_id or not new_state_id:
                logger.warning(f"Dati incompleti per sync order state: order_id={order_id}, new_state_id={new_state_id}")
                return
            
            # Recupera id_store dall'ordine
            db = next(get_db())
            try:
                from src.models.order import Order
                from src.repository.order_repository import OrderRepository
                
                order_repo = OrderRepository(db)
                order = order_repo.get_by_id(order_id)
                
                if not order:
                    logger.warning(f"Ordine {order_id} non trovato")
                    return
                
                if not order.id_store:
                    logger.warning(f"Ordine {order_id} non ha id_store associato")
                    return
                
                id_store = order.id_store
                
                # Query trigger attivi per questo evento e store
                trigger_repo = PlatformStateTriggerRepository(db)
                triggers = trigger_repo.get_active_triggers_by_event(
                    event_type=EventType.ORDER_STATUS_CHANGED.value,
                    id_store=id_store
                )
                
                # Cerca trigger che matcha new_state_id e state_type
                matching_trigger = None
                for trigger in triggers:
                    if trigger.state_type == 'order_state' and trigger.id_state_local == new_state_id:
                        matching_trigger = trigger
                        break
                
                if not matching_trigger:
                    logger.debug(f"Nessun trigger trovato per order_id={order_id}, state_id={new_state_id}, store={id_store}")
                    return
                
                # Recupera id_platform_state da ecommerce_order_states
                from src.models.ecommerce_order_state import EcommerceOrderState
                ecommerce_state = db.query(EcommerceOrderState).filter(
                    EcommerceOrderState.id_ecommerce_order_state == matching_trigger.id_state_platform
                ).first()
                
                if not ecommerce_state:
                    logger.warning(f"EcommerceOrderState {matching_trigger.id_state_platform} non trovato")
                    return
                
                # Sincronizza con piattaforma usando l'ID PrestaShop reale
                success = await self._sync_to_platform(
                    order_id=order_id,
                    platform_state_id=ecommerce_state.id_platform_state,
                    id_store=id_store
                )
                
                # Aggiorna order.id_ecommerce_state se sincronizzazione riuscita
                if success:
                    order.id_ecommerce_state = matching_trigger.id_state_platform
                    db.commit()
                    logger.info(f"Updated order {order_id}.id_ecommerce_state to {matching_trigger.id_state_platform}")
                
            finally:
                db.close()
                
        except Exception as e:
            # Non rethrow - plugin non deve bloccare flusso principale
            logger.error(f"Errore sync order state per order_id={event.data.get('order_id')}: {str(e)}", exc_info=True)
    
    async def _sync_shipping_state(self, event: Event) -> None:
        """
        Sincronizza stato spedizione con piattaforma.
        
        Args:
            event: Event SHIPPING_STATUS_CHANGED con id_shipping, id_order, old_state_id, new_state_id
        """
        try:
            id_shipping = event.data.get('id_shipping')
            id_order = event.data.get('id_order')
            new_state_id = event.data.get('new_state_id')
            
            if not id_order or not new_state_id:
                logger.warning(f"Dati incompleti per sync shipping state: id_order={id_order}, new_state_id={new_state_id}")
                return
            
            # Recupera id_store dall'ordine
            db = next(get_db())
            try:
                from src.models.order import Order
                from src.repository.order_repository import OrderRepository
                
                order_repo = OrderRepository(db)
                order = order_repo.get_by_id(id_order)
                
                if not order:
                    logger.warning(f"Ordine {id_order} non trovato")
                    return
                
                if not order.id_store:
                    logger.warning(f"Ordine {id_order} non ha id_store associato")
                    return
                
                id_store = order.id_store
                
                # Query trigger attivi per questo evento e store
                trigger_repo = PlatformStateTriggerRepository(db)
                triggers = trigger_repo.get_active_triggers_by_event(
                    event_type=EventType.SHIPPING_STATUS_CHANGED.value,
                    id_store=id_store
                )
                
                # Cerca trigger che matcha new_state_id e state_type
                matching_trigger = None
                for trigger in triggers:
                    if trigger.state_type == 'shipping_state' and trigger.id_state_local == new_state_id:
                        matching_trigger = trigger
                        break
                
                if not matching_trigger:
                    logger.debug(f"Nessun trigger trovato per shipping_id={id_shipping}, state_id={new_state_id}, store={id_store}")
                    return
                
                # Recupera id_platform_state da ecommerce_order_states
                from src.models.ecommerce_order_state import EcommerceOrderState
                ecommerce_state = db.query(EcommerceOrderState).filter(
                    EcommerceOrderState.id_ecommerce_order_state == matching_trigger.id_state_platform
                ).first()
                
                if not ecommerce_state:
                    logger.warning(f"EcommerceOrderState {matching_trigger.id_state_platform} non trovato")
                    return
                
                # Per shipping, sincronizziamo lo stato dell'ordine associato
                # (PrestaShop non ha stati shipping separati, usa order_state)
                success = await self._sync_to_platform(
                    order_id=id_order,
                    platform_state_id=ecommerce_state.id_platform_state,
                    id_store=id_store
                )
                
                # Aggiorna order.id_ecommerce_state se sincronizzazione riuscita
                if success:
                    order.id_ecommerce_state = matching_trigger.id_state_platform
                    db.commit()
                    logger.info(f"Updated order {id_order}.id_ecommerce_state to {matching_trigger.id_state_platform}")
                
            finally:
                db.close()
                
        except Exception as e:
            # Non rethrow - plugin non deve bloccare flusso principale
            logger.error(f"Errore sync shipping state per shipping_id={event.data.get('id_shipping')}: {str(e)}", exc_info=True)
    
    async def _sync_to_platform(self, order_id: int, platform_state_id: int, id_store: int) -> bool:
        """
        Sincronizza stato ordine con piattaforma ecommerce.
        
        Args:
            order_id: ID ordine locale
            platform_state_id: ID stato sulla piattaforma remota
            id_store: ID dello store
            
        Returns:
            True se sincronizzazione riuscita, False altrimenti
        """
        try:
            from src.services.ecommerce.service_factory import create_ecommerce_service
            from src.database import get_db
            
            db = next(get_db())
            try:
                # Usa factory per ottenere il service corretto in base allo store
                ecommerce_service = create_ecommerce_service(id_store, db)
                
                async with ecommerce_service:
                    success = await ecommerce_service.sync_order_state_to_platform(
                        order_id=order_id,
                        platform_state_id=platform_state_id
                    )
                    if success:
                        logger.info(
                            f"Stato ordine {order_id} sincronizzato con successo a store {id_store} "
                            f"(platform_state_id={platform_state_id})"
                        )
                    else:
                        logger.warning(
                            f"Fallita sincronizzazione stato ordine {order_id} a store {id_store}"
                        )
                    return success
            finally:
                db.close()
                
        except Exception as e:
            # Non rethrow - plugin non deve bloccare flusso principale
            logger.error(f"Errore sync to platform per order_id={order_id}, store={id_store}: {str(e)}", exc_info=True)
            return False

