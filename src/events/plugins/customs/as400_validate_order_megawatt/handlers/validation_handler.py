"""Handler per la validazione ordini AS400."""

import logging
from sqlalchemy.orm import Session
from src.events.interfaces.base_event_handler import BaseEventHandler
from src.events.core.event import Event, EventType
from src.database import SessionLocal
from ..services.soap_client import AS400SoapClient
from ..services.order_service import OrderDataService
from ..config.settings import TEST_MODE

logger = logging.getLogger("as400_validate_order_megawatt")


class AS400ValidationHandler(BaseEventHandler):
    """Handler per validare ordini con AS400 quando lo stato cambia da 1 a 2."""

    def __init__(self):
        """Inizializza l'handler."""
        super().__init__(name="as400_validation_handler")

    def can_handle(self, event: Event) -> bool:
        """
        Verifica se l'handler può processare questo evento.
        
        Gestisce solo eventi ORDER_STATUS_CHANGED dove:
        - old_state_id == 1
        - new_state_id == 2
        """
        logger.info(f"[AS400] can_handle chiamato per evento: type={event.event_type}")
        logger.info(f"[AS400] Dati evento: {event.data}")
        
        if event.event_type != EventType.ORDER_STATUS_CHANGED.value:
            logger.debug(f"[AS400] Evento non è ORDER_STATUS_CHANGED, tipo: {event.event_type}")
            return False
        
        old_state_id = event.data.get("old_state_id")
        new_state_id = event.data.get("new_state_id")
        
        logger.info(f"[AS400] old_state_id={old_state_id} (type: {type(old_state_id)}), new_state_id={new_state_id} (type: {type(new_state_id)})")
        
        can_handle_result = old_state_id == 1 and new_state_id == 2
        logger.info(f"[AS400] can_handle result: {can_handle_result}")
        
        return can_handle_result

    async def handle(self, event: Event) -> None:
        """
        Gestisce l'evento di cambio stato ordine.
        
        Processo:
        1. Carica ordine con tutte le relazioni
        2. Se TEST_MODE=1: logga XML e ritorna
        3. Se TEST_MODE=0: invia ad AS400
        4. In base alla risposta:
           - stampataDistinta="S": conferma stato 2
           - stampataDistinta="N": rollback a stato 1
           - Errore: rollback a stato 1
        """
        logger.info(f"[AS400] ════════════════════════════════════════════════════")
        logger.info(f"[AS400] handle() CHIAMATO per evento: {event.event_type}")
        logger.info(f"[AS400] Dati evento completi: {event.data}")
        logger.info(f"[AS400] Metadata evento: {event.metadata}")
        
        order_id = event.data.get("order_id")
        old_state_id = event.data.get("old_state_id")
        
        logger.info(f"[AS400] order_id={order_id}, old_state_id={old_state_id}")
        
        if not order_id:
            logger.warning("ID ordine non trovato nei dati dell'evento")
            return
        
        logger.info(f"Elaborazione validazione AS400 per ordine {order_id}")
        
        session: Session = None
        try:
            session = SessionLocal()
            order_service = OrderDataService(session)
            
            # Carica ordine con tutte le relazioni
            order = order_service.get_order_for_validation(order_id)
            
            if not order:
                logger.warning(f"Ordine {order_id} non trovato")
                return

            # Se lo stato è già 2, non eseguire nulla
            if old_state_id == 2:
                logger.info(f"Ordine {order_id} è già nello stato 2, nessuna operazione necessaria")
                return
            
            # Se TEST_MODE=1, solo log XML e ritorna (modalità test)
            if TEST_MODE == 1:
                soap_client = AS400SoapClient(order_service)
                order_xml = soap_client.xml_builder.build_order_xml(order)
                logger.info(f"TEST_MODE=1: XML generato per ordine {order_id} (non inviato - modalità test)")
                logger.info(f"XML ordine:\n{order_xml}")
                return
            
            # TEST_MODE=0: Invia ad AS400 (modalità produzione)
            logger.info(f"TEST_MODE=0: Invio ordine {order_id} ad AS400")
            
            soap_client = AS400SoapClient(order_service)
            response = soap_client.send_order(order)
            
            stampata_distinta = response.get("stampataDistinta", "").upper()
            numero_ordine = response.get("numeroOrdine", "")
            messaggio_errore = response.get("messaggioErrore", "")
            
            logger.info(
                f"Risposta AS400 per ordine {order_id}: "
                f"stampataDistinta={stampata_distinta}, "
                f"numeroOrdine={numero_ordine}, "
                f"messaggioErrore={messaggio_errore}"
            )
            
            # Gestisci risposta
            if stampata_distinta == "S":
                # Tutti i prodotti disponibili: conferma stato 2
                logger.info(f"Ordine {order_id} validato: conferma stato 2")
                order.id_order_state = 2
                session.add(order)
                session.commit()
                logger.info(f"Ordine {order_id} stato confermato a 2")
                
            elif stampata_distinta == "N":
                # Prodotti non disponibili: rollback a stato 1
                logger.warning(
                    f"Validazione ordine {order_id} fallita: prodotti non disponibili. "
                    f"Rollback a stato 1"
                )
                order.id_order_state = 1
                session.add(order)
                session.commit()
                logger.info(f"Ordine {order_id} stato ripristinato a 1")
                
            else:
                # Risposta inattesa: rollback a stato 1
                logger.error(
                    f"Ordine {order_id} ha ricevuto risposta inattesa: "
                    f"stampataDistinta={stampata_distinta}. Rollback a stato 1"
                )
                order.id_order_state = 1
                session.add(order)
                session.commit()
                logger.info(f"Ordine {order_id} stato ripristinato a 1 per errore")
                
        except Exception as e:
            logger.exception(f"Errore durante elaborazione ordine {order_id}: {e}")
            
            # In caso di errore, rollback stato a 1
            if session:
                try:
                    from src.models.order import Order
                    order_to_rollback = session.query(Order).filter(Order.id_order == order_id).first()
                    if order_to_rollback:
                        logger.warning(f"Ripristino ordine {order_id} a stato 1 per errore")
                        order_to_rollback.id_order_state = 1
                        session.add(order_to_rollback)
                        session.commit()
                        logger.info(f"Ordine {order_id} stato ripristinato a 1")
                except Exception as rollback_error:
                    logger.error(f"Errore durante rollback per ordine {order_id}: {rollback_error}")
                    if session:
                        session.rollback()
            
        finally:
            if session:
                session.close()

