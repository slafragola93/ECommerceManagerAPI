"""
Platform State Sync Event Handlers

Gestisce ORDER_STATUS_CHANGED e SHIPPING_STATUS_CHANGED per sincronizzare stati con piattaforme.
"""
from __future__ import annotations

import logging
from typing import Optional
from dataclasses import dataclass
from contextlib import contextmanager

from src.events.core.event import Event, EventType
from src.events.interfaces import BaseEventHandler
from src.models.ecommerce_order_state import EcommerceOrderState
from src.models.order import Order
from src.database import get_db
from src.repository.platform_state_trigger_repository import PlatformStateTriggerRepository
from src.repository.order_repository import OrderRepository
from src.services.ecommerce.service_factory import create_ecommerce_service

logger = logging.getLogger(__name__)


@dataclass
class StateSyncContext:
    """Contesto per la sincronizzazione di stato."""
    order_id: int
    new_state_id: int
    state_type: str  # 'order_state' o 'shipping_state'
    event_type: str


class OrderValidator:
    """Validatore per ordini e loro stati."""
    
    @staticmethod
    def is_valid_for_sync(order: Optional[Order]) -> bool:
        """Verifica se un ordine può essere sincronizzato con la piattaforma."""
        if not order:
            logger.warning("Ordine non trovato")
            return False
            
        if not order.id_store:
            logger.warning(f"Ordine {order.id_order} senza id_store")
            return False
            
        if not order.id_platform or order.id_platform == 0:
            logger.debug(f"Ordine {order.id_order} senza id_platform valido")
            return False
            
        return True


class PlatformStateMatcher:
    """Gestisce il matching tra stati locali e stati piattaforma."""
    
    def __init__(self, trigger_repo: PlatformStateTriggerRepository, db):
        self.trigger_repo = trigger_repo
        self.db = db
    
    def find_matching_trigger(
        self, 
        event_type: str, 
        id_store: int, 
        state_type: str, 
        state_id: int
    ):
        """Trova il trigger attivo che corrisponde allo stato locale."""
        triggers = self.trigger_repo.get_active_triggers_by_event(
            event_type=event_type,
            id_store=id_store
        )
        
        for trigger in triggers:
            if trigger.state_type == state_type and trigger.id_state_local == state_id:
                return trigger
        
        logger.debug(
            f"Nessun trigger per event={event_type}, store={id_store}, "
            f"state_type={state_type}, state_id={state_id}"
        )
        return None
    
    def get_platform_state_id(self, id_state_platform: int) -> Optional[int]:
        """Recupera l'ID stato piattaforma da ecommerce_order_states."""
        ecommerce_state = self.db.query(EcommerceOrderState).filter(
            EcommerceOrderState.id_ecommerce_order_state == id_state_platform
        ).first()
        
        if not ecommerce_state:
            logger.warning(f"EcommerceOrderState {id_state_platform} non trovato")
            return None
            
        return ecommerce_state.id_platform_state


class PlatformSyncService:
    """Servizio per la sincronizzazione con piattaforme ecommerce."""
    
    async def sync_order_state(
        self, 
        order_id: int, 
        platform_state_id: int, 
        id_store: int
    ) -> bool:
        """Sincronizza stato ordine con piattaforma ecommerce."""
        try:
            with self._get_db_session() as db:
                ecommerce_service = create_ecommerce_service(id_store, db)
                
                async with ecommerce_service:
                    success = await ecommerce_service.sync_order_state_to_platform(
                        order_id=order_id,
                        platform_state_id=platform_state_id
                    )
                    
                    self._log_sync_result(success, order_id, id_store, platform_state_id)
                    return success
                    
        except Exception as e:
            logger.error(
                f"Errore sync piattaforma: order={order_id}, store={id_store}: {e}", 
                exc_info=True
            )
            return False
    
    @contextmanager
    def _get_db_session(self):
        """Context manager per gestione sessione DB."""
        db = next(get_db())
        try:
            yield db
        finally:
            db.close()
    
    @staticmethod
    def _log_sync_result(success: bool, order_id: int, id_store: int, platform_state_id: int):
        """Log del risultato della sincronizzazione."""
        if success:
            logger.info(
                f"Sincronizzazione riuscita: order={order_id}, store={id_store}, "
                f"platform_state={platform_state_id}"
            )
        else:
            logger.warning(
                f"Sincronizzazione fallita: order={order_id}, store={id_store}"
            )


class StateUpdateOrchestrator:
    """Orchestratore per l'aggiornamento degli stati."""
    
    def __init__(self, db):
        self.db = db
        self.order_repo = OrderRepository(db)
        self.validator = OrderValidator()
        self.matcher = PlatformStateMatcher(PlatformStateTriggerRepository(db), db)
        self.sync_service = PlatformSyncService()
    
    async def process_state_change(self, context: StateSyncContext) -> None:
        """Processa un cambio di stato e lo sincronizza con la piattaforma."""
        order = self.order_repo.get_by_id(context.order_id)
        
        if not self.validator.is_valid_for_sync(order):
            return
        
        trigger = self.matcher.find_matching_trigger(
            event_type=context.event_type,
            id_store=order.id_store,
            state_type=context.state_type,
            state_id=context.new_state_id
        )
        
        if not trigger:
            return
        
        platform_state_id = self.matcher.get_platform_state_id(trigger.id_state_platform)
        
        if not platform_state_id:
            return
        
        success = await self.sync_service.sync_order_state(
            order_id=context.order_id,
            platform_state_id=platform_state_id,
            id_store=order.id_store
        )
        
        if success:
            self._update_order_ecommerce_state(order, trigger.id_state_platform)
    
    def _update_order_ecommerce_state(self, order: Order, id_state_platform: int):
        """Aggiorna lo stato ecommerce dell'ordine."""
        order.id_ecommerce_state = id_state_platform
        self.db.commit()
        logger.info(
            f"Aggiornato order {order.id_order}.id_ecommerce_state -> {id_state_platform}"
        )


class PlatformStateSyncHandler(BaseEventHandler):
    """
    Handler che sincronizza stati ordini/spedizioni con piattaforme ecommerce.
    
    Questo è il punto di ingresso principale chiamato dal sistema di eventi.
    """
    
    SUPPORTED_EVENTS = {
        EventType.ORDER_STATUS_CHANGED.value,
        EventType.SHIPPING_STATUS_CHANGED.value
    }
    
    def __init__(self, *, name: str = "platform_state_sync_handler") -> None:
        super().__init__(name=name)
    
    def can_handle(self, event: Event) -> bool:
        """Verifica se questo handler può gestire l'evento."""
        return event.event_type in self.SUPPORTED_EVENTS
    
    async def handle(self, event: Event) -> None:
        """
        Punto di ingresso principale - chiamato dal sistema di eventi.
        
        Gestisce eventi ORDER_STATUS_CHANGED o SHIPPING_STATUS_CHANGED
        delegando l'elaborazione all'orchestratore.
        """
        try:
            context = self._build_context(event)
            if not context:
                return
            
            await self._execute_state_sync(context)
                
        except Exception as e:
            logger.error(f"Errore in {self.name}: {e}", exc_info=True)
            # Non solleva eccezione - plugin non deve bloccare flusso principale
    
    async def _execute_state_sync(self, context: StateSyncContext) -> None:
        """Esegue la sincronizzazione dello stato."""
        with self._get_db_session() as db:
            orchestrator = StateUpdateOrchestrator(db)
            await orchestrator.process_state_change(context)
    
    def _build_context(self, event: Event) -> Optional[StateSyncContext]:
        """Costruisce il contesto di sincronizzazione dall'evento."""
        order_id = event.data.get('order_id') or event.data.get('id_order')
        new_state_id = event.data.get('new_state_id')
        
        if not order_id or not new_state_id:
            logger.warning(
                f"Dati incompleti: order_id={order_id}, new_state_id={new_state_id}"
            )
            return None
        
        state_type = (
            'order_state' 
            if event.event_type == EventType.ORDER_STATUS_CHANGED.value 
            else 'shipping_state'
        )
        
        return StateSyncContext(
            order_id=order_id,
            new_state_id=new_state_id,
            state_type=state_type,
            event_type=event.event_type
        )
    
    @contextmanager
    def _get_db_session(self):
        """Context manager per gestione sessione DB."""
        db = next(get_db())
        try:
            yield db
        finally:
            db.close()