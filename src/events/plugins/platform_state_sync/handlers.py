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
        if event.event_type == EventType.ORDER_STATUS_CHANGED.value:
            await self._sync_order_state(event)
        elif event.event_type == EventType.SHIPPING_STATUS_CHANGED.value:
            await self._sync_shipping_state(event)
    
    async def _sync_order_state(self, event: Event) -> None:
        """
        Sincronizza stato ordine con piattaforma.
        
        Args:
            event: Event ORDER_STATUS_CHANGED con order_id, old_state_id, new_state_id
        """
        try:
            order_id = event.data.get('order_id')
            new_state_id = event.data.get('new_state_id')
            id_platform = event.data.get('id_platform')
            
            if not order_id or not new_state_id or not id_platform:
                logger.warning(f"Dati incompleti per sync order state: order_id={order_id}, new_state_id={new_state_id}, id_platform={id_platform}")
                return
            
            # Query trigger attivi per questo evento e piattaforma
            db = next(get_db())
            try:
                trigger_repo = PlatformStateTriggerRepository(db)
                triggers = trigger_repo.get_active_triggers_by_event(
                    event_type=EventType.ORDER_STATUS_CHANGED.value,
                    id_platform=id_platform
                )
                
                # Cerca trigger che matcha new_state_id e state_type
                matching_trigger = None
                for trigger in triggers:
                    if trigger.state_type == 'order_state' and trigger.id_state_local == new_state_id:
                        matching_trigger = trigger
                        break
                
                if not matching_trigger:
                    logger.debug(f"Nessun trigger trovato per order_id={order_id}, state_id={new_state_id}, platform={id_platform}")
                    return
                
                # Sincronizza con piattaforma
                await self._sync_to_platform(
                    order_id=order_id,
                    platform_state_id=matching_trigger.id_state_platform,
                    id_platform=id_platform
                )
                
            finally:
                db.close()
                
        except Exception as e:
            # Non rethrow - plugin non deve bloccare flusso principale
            logger.error(f"Errore sync order state per order_id={event.data.get('order_id')}: {str(e)}")
    
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
            id_platform = event.data.get('id_platform')
            
            if not id_order or not new_state_id or not id_platform:
                logger.warning(f"Dati incompleti per sync shipping state: id_order={id_order}, new_state_id={new_state_id}, id_platform={id_platform}")
                return
            
            # Query trigger attivi per questo evento e piattaforma
            db = next(get_db())
            try:
                trigger_repo = PlatformStateTriggerRepository(db)
                triggers = trigger_repo.get_active_triggers_by_event(
                    event_type=EventType.SHIPPING_STATUS_CHANGED.value,
                    id_platform=id_platform
                )
                
                # Cerca trigger che matcha new_state_id e state_type
                matching_trigger = None
                for trigger in triggers:
                    if trigger.state_type == 'shipping_state' and trigger.id_state_local == new_state_id:
                        matching_trigger = trigger
                        break
                
                if not matching_trigger:
                    logger.debug(f"Nessun trigger trovato per shipping_id={id_shipping}, state_id={new_state_id}, platform={id_platform}")
                    return
                
                # Per shipping, sincronizziamo lo stato dell'ordine associato
                # (PrestaShop non ha stati shipping separati, usa order_state)
                await self._sync_to_platform(
                    order_id=id_order,
                    platform_state_id=matching_trigger.id_state_platform,
                    id_platform=id_platform
                )
                
            finally:
                db.close()
                
        except Exception as e:
            # Non rethrow - plugin non deve bloccare flusso principale
            logger.error(f"Errore sync shipping state per shipping_id={event.data.get('id_shipping')}: {str(e)}")
    
    async def _sync_to_platform(self, order_id: int, platform_state_id: int, id_platform: int) -> None:
        """
        Sincronizza stato ordine con piattaforma ecommerce.
        
        Args:
            order_id: ID ordine locale
            platform_state_id: ID stato sulla piattaforma remota
            id_platform: ID piattaforma
        """
        try:
            # Per ora supportiamo solo PrestaShop (id_platform=1)
            # In futuro si può estendere con factory pattern
            if id_platform == 1:
                from src.services.ecommerce.prestashop_service import PrestaShopService
                from src.database import get_db
                
                db = next(get_db())
                try:
                    async with PrestaShopService(db, platform_id=id_platform) as prestashop_service:
                        success = await prestashop_service.sync_order_state_to_platform(
                            order_id=order_id,
                            platform_state_id=platform_state_id
                        )
                        if success:
                            logger.info(
                                f"Stato ordine {order_id} sincronizzato con successo a piattaforma {id_platform} "
                                f"(platform_state_id={platform_state_id})"
                            )
                        else:
                            logger.warning(
                                f"Fallita sincronizzazione stato ordine {order_id} a piattaforma {id_platform}"
                            )
                finally:
                    db.close()
            else:
                logger.debug(f"Piattaforma {id_platform} non supportata per sync stati")
                
        except Exception as e:
            # Non rethrow - plugin non deve bloccare flusso principale
            logger.error(f"Errore sync to platform per order_id={order_id}, platform={id_platform}: {str(e)}")

