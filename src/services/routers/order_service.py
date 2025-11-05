"""
Order Service per gestione logica business ordini seguendo principi SOLID
"""
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from src.services.interfaces.order_service_interface import IOrderService
from src.repository.order_repository import OrderRepository
from src.models.order_state import OrderState
from src.models.relations.relations import orders_history
from src.schemas.order_schema import (
    OrderUpdateSchema,
    OrderStatusUpdateItem,
    BulkOrderStatusUpdateResponseSchema,
    OrderStatusUpdateResult,
    OrderStatusUpdateError
)
from src.events.decorators import emit_event_on_success
from src.events.core.event import EventType
import logging

logger = logging.getLogger(__name__)


# Funzioni helper per estrazione dati eventi
def _extract_order_status_data(*args, result=None, **kwargs):
    """Estrae i dati dell'evento di cambio stato ordine."""
    if not isinstance(result, dict) or result.get("old_state_id") is None:
        return None
    
    # Prendi order_id da result o kwargs
    order_id = result.get("order_id") or kwargs.get("order_id")
    
    # Prendi new_state_id da result (può essere "new_status_id" o "new_state_id")
    new_state_id = result.get("new_state_id") or result.get("new_status_id") or kwargs.get("new_status_id")
    
    return {
        "order_id": order_id,
        "old_state_id": result.get("old_state_id"),
        "new_state_id": new_state_id,
    }


def _should_emit_order_status_event(*args, result=None, **kwargs):
    """Verifica se l'evento di cambio stato deve essere emesso."""
    return isinstance(result, dict) and result.get("old_state_id") is not None


def _extract_order_update_status_data(*args, result=None, **kwargs):
    """Estrae i dati dell'evento di cambio stato da update_order."""
    if not isinstance(result, dict):
        return None
    
    old_state_id = result.get("old_state_id")
    new_state_id = result.get("new_state_id")
    order_id = result.get("order_id") or kwargs.get("order_id")
    
    if old_state_id is None or new_state_id is None or order_id is None:
        return None
        
    return {
        "order_id": order_id,
        "old_state_id": old_state_id,
        "new_state_id": new_state_id,
    }


def _should_emit_order_update_status_event(*args, result=None, **kwargs):
    """Verifica se l'evento di cambio stato deve essere emesso da update_order."""
    if not isinstance(result, dict):
        return False
    
    old_state_id = result.get("old_state_id")
    new_state_id = result.get("new_state_id")
    
    return (
        old_state_id is not None 
        and new_state_id is not None 
        and old_state_id != new_state_id
    )


def _extract_bulk_order_status_data(*args, result=None, **kwargs):
    """Estrae i dati dell'evento di cambio stato da bulk update."""
    if not isinstance(result, dict):
        return None
    
    old_state_id = result.get("old_state_id")
    new_state_id = result.get("new_state_id")
    order_id = result.get("order_id")
    
    if old_state_id is None or new_state_id is None or order_id is None:
        return None
        
    return {
        "order_id": order_id,
        "old_state_id": old_state_id,
        "new_state_id": new_state_id,
    }


def _should_emit_bulk_order_status_event(*args, result=None, **kwargs):
    """Verifica se l'evento di cambio stato deve essere emesso da bulk update."""
    if not isinstance(result, dict):
        return False
    
    old_state_id = result.get("old_state_id")
    new_state_id = result.get("new_state_id")
    
    return (
        old_state_id is not None 
        and new_state_id is not None 
        and old_state_id != new_state_id
    )


@emit_event_on_success(
    event_type=EventType.ORDER_STATUS_CHANGED,
    data_extractor=_extract_bulk_order_status_data,
    condition=_should_emit_bulk_order_status_event,
    source="order_service.update_single_order_status_in_bulk",
)
async def _update_single_order_status_in_bulk(
    order_id: int,
    new_state_id: int,
    or_repo: OrderRepository
) -> Dict[str, Any]:
    """
    Helper function per aggiornare lo stato di un singolo ordine nel contesto bulk.
    Usata dal bulk update per ogni ordine.
    
    Args:
        order_id: ID dell'ordine
        new_state_id: Nuovo stato dell'ordine
        or_repo: Repository ordini
        
    Returns:
        Dict con order_id, old_state_id, new_state_id per emissione evento
    """
    order = or_repo.get_by_id(_id=order_id)
    if order is None:
        raise ValueError(f"Ordine {order_id} non trovato")
    
    old_state_id = order.id_order_state
    if old_state_id == new_state_id:
        raise ValueError(f"Ordine {order_id} è già nello stato {new_state_id}")
    
    # Aggiornare stato
    order.id_order_state = new_state_id
    or_repo.session.add(order)
    
    # Creare record in orders_history
    order_history_insert = orders_history.insert().values(
        id_order=order_id,
        id_order_state=new_state_id,
        date_add=datetime.now()
    )
    or_repo.session.execute(order_history_insert)
    
    # Commit per questo ordine
    or_repo.session.commit()
    
    # Return result con dati per emissione evento
    return {
        "order_id": order_id,
        "old_state_id": old_state_id,
        "new_state_id": new_state_id,
    }


class OrderService(IOrderService):
    """Order Service per gestione logica business ordini"""
    
    def __init__(self, order_repository: OrderRepository):
        self._order_repository = order_repository
    
    async def validate_business_rules(self, data: Any) -> None:
        """
        Valida le regole business per gli ordini.
        Questo metodo è richiesto dall'interfaccia IBaseService.
        
        Args:
            data: Dati da validare (può essere qualsiasi tipo)
        """
        # Per ora non ci sono regole business specifiche da validare
        # Questo metodo può essere esteso in futuro se necessario
        pass
    
    @emit_event_on_success(
        event_type=EventType.ORDER_STATUS_CHANGED,
        data_extractor=_extract_order_status_data,
        condition=_should_emit_order_status_event,
        source="order_service.update_order_status",
    )
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
        order = self._order_repository.get_by_id(_id=order_id)
        if order is None:
            raise ValueError(f"Ordine {order_id} non trovato")

        old_state_id = order.id_order_state
        if old_state_id == new_status_id:
            return {
                "message": "Stato ordine aggiornato con successo",
                "order_id": order_id,
                "new_status_id": new_status_id,
            }

        order.id_order_state = new_status_id
        self._order_repository.session.add(order)

        order_history_insert = orders_history.insert().values(
            id_order=order_id,
            id_order_state=new_status_id,
            date_add=datetime.now()
        )
        self._order_repository.session.execute(order_history_insert)
        self._order_repository.session.commit()

        return {
            "message": "Stato ordine aggiornato con successo",
            "order_id": order_id,
            "new_status_id": new_status_id,
            "old_state_id": old_state_id,
        }
    
    @emit_event_on_success(
        event_type=EventType.ORDER_STATUS_CHANGED,
        data_extractor=_extract_order_update_status_data,
        condition=_should_emit_order_update_status_event,
        source="order_service.update_order",
    )
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
        order = self._order_repository.get_by_id(_id=order_id)
        if order is None:
            raise ValueError(f"Ordine {order_id} non trovato")

        # Salvare vecchio stato prima dell'aggiornamento
        old_state_id = order.id_order_state
        
        # Verificare se id_order_state viene aggiornato
        new_state_id = None
        if hasattr(order_schema, 'id_order_state') and order_schema.id_order_state is not None:
            new_state_id = order_schema.id_order_state
        
        self._order_repository.update(edited_order=order, data=order_schema)
        
        # Restituire risultato con old_state_id se lo stato è cambiato
        if new_state_id is not None and new_state_id != old_state_id:
            return {
                "message": "Ordine aggiornato con successo",
                "order_id": order_id,
                "old_state_id": old_state_id,
                "new_state_id": new_state_id,
            }
        
        return {
            "message": "Ordine aggiornato con successo",
            "order_id": order_id
        }
    
    async def bulk_update_order_status(
        self, 
        updates: List[OrderStatusUpdateItem]
    ) -> BulkOrderStatusUpdateResponseSchema:
        """
        Aggiorna gli stati di più ordini in modo massivo.
        
        La logica business include:
        - Validazione stati nella tabella order_states
        - Verifica esistenza ordini
        - Verifica che lo stato sia diverso da quello corrente
        - Aggiornamento stato e creazione record in orders_history
        - Emissione eventi ORDER_STATUS_CHANGED per ogni cambio valido
        
        Args:
            updates: Lista di aggiornamenti stato ordine
            
        Returns:
            Risposta con successi, fallimenti e summary
        """
        successful: List[OrderStatusUpdateResult] = []
        failed: List[OrderStatusUpdateError] = []
        db = self._order_repository.session
        
        # 1. Validare stati: raccogliere tutti gli stati unici e verificare esistenza
        unique_state_ids = list(set(item.id_order_state for item in updates))
        valid_states = {
            state.id_order_state 
            for state in db.query(OrderState)
                .filter(OrderState.id_order_state.in_(unique_state_ids))
                .all()
        }
        
        # Aggiungere errori per stati non validi
        invalid_states = set(unique_state_ids) - valid_states
        if invalid_states:
            for item in updates:
                if item.id_order_state in invalid_states:
                    failed.append(OrderStatusUpdateError(
                        id_order=item.id_order,
                        error="INVALID_STATE",
                        reason=f"Stato {item.id_order_state} non esiste nella tabella order_states"
                    ))
        
        # 2. Processare ogni ordine
        for item in updates:
            # Skip se già fallito per stato non valido
            if item.id_order_state in invalid_states:
                continue
                
            try:
                # Usare funzione helper con decorator per aggiornare ordine ed emettere evento
                result = await _update_single_order_status_in_bulk(
                    order_id=item.id_order,
                    new_state_id=item.id_order_state,
                    or_repo=self._order_repository
                )
                
                # Aggiungere a successi
                successful.append(OrderStatusUpdateResult(
                    id_order=result["order_id"],
                    old_state_id=result["old_state_id"],
                    new_state_id=result["new_state_id"]
                ))
                
            except ValueError as e:
                # Errore di validazione (ordine non trovato o stato già impostato)
                error_msg = str(e)
                if "non trovato" in error_msg:
                    error_type = "ORDER_NOT_FOUND"
                elif "è già nello stato" in error_msg:
                    error_type = "STATE_ALREADY_SET"
                else:
                    error_type = "VALIDATION_ERROR"
                
                failed.append(OrderStatusUpdateError(
                    id_order=item.id_order,
                    error=error_type,
                    reason=error_msg
                ))
                
            except Exception as e:
                # Rollback in caso di errore
                self._order_repository.session.rollback()
                logger.error(
                    f"Errore durante aggiornamento stato ordine {item.id_order}: {e}",
                    exc_info=True
                )
                failed.append(OrderStatusUpdateError(
                    id_order=item.id_order,
                    error="UPDATE_ERROR",
                    reason=f"Errore durante aggiornamento: {str(e)}"
                ))
        
        # 3. Preparare risposta
        total = len(updates)
        successful_count = len(successful)
        failed_count = len(failed)
        
        return BulkOrderStatusUpdateResponseSchema(
            successful=successful,
            failed=failed,
            summary={
                "total": total,
                "successful_count": successful_count,
                "failed_count": failed_count
            }
        )
