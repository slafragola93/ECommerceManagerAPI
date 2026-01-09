"""
Servizio per polling periodico automatico del tracking di tutte le spedizioni
"""
import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.engine import Row

from src.repository.shipping_repository import ShippingRepository
from src.factories.services.carrier_service_factory import CarrierServiceFactory
from src.repository.api_carrier_repository import ApiCarrierRepository
from src.models.carrier_api import CarrierTypeEnum

logger = logging.getLogger(__name__)

# Configurazione intervalli polling (in secondi)
BRT_INITIAL_POLLING_INTERVAL = 450  # 7.5 minuti (media tra 5-10)
BRT_POST_RESPONSE_POLLING_INTERVAL = 5400  # 1.5 ore (media tra 1-2)
BRT_RATE_LIMIT_SECONDS = 300  # 5 minuti

DEFAULT_POLLING_INTERVAL = 3600  # 1 ora
DEFAULT_RATE_LIMIT_SECONDS = 60  # 1 minuto

EXCLUDED_SHIPPING_STATES = [1, 8, 11, 13]  # Stati finali esclusi dal polling

# Configurazione per carrier
CARRIER_POLLING_CONFIG = {
    CarrierTypeEnum.BRT.value: {
        "initial_interval": BRT_INITIAL_POLLING_INTERVAL,
        "post_response_interval": BRT_POST_RESPONSE_POLLING_INTERVAL,
        "rate_limit": BRT_RATE_LIMIT_SECONDS
    },
    CarrierTypeEnum.DHL.value: {
        "interval": DEFAULT_POLLING_INTERVAL,
        "rate_limit": DEFAULT_RATE_LIMIT_SECONDS
    },
    CarrierTypeEnum.FEDEX.value: {
        "interval": DEFAULT_POLLING_INTERVAL,
        "rate_limit": DEFAULT_RATE_LIMIT_SECONDS
    }
}

# Rate limiting in-memory: {carrier_type: {tracking_number: last_request_timestamp}}
_last_tracking_request: Dict[str, Dict[str, float]] = {}


async def poll_tracking_periodic(db: Session):
    """
    Funzione principale per il polling periodico del tracking.
    
    Recupera tutte le spedizioni con tracking, le raggruppa per carrier,
    e chiama il tracking service appropriato per ogni gruppo.
    
    Args:
        db: Database session
    """
    try:
        logger.info("Starting periodic tracking polling")
        
        # Recupera tutte le spedizioni con tracking (escludendo stati finali)
        shipping_repo = ShippingRepository(db)
        shipments = shipping_repo.get_shipments_with_tracking(exclude_states=EXCLUDED_SHIPPING_STATES)
        
        if not shipments:
            logger.info("No shipments with tracking found, skipping polling")
            return
        
        logger.info(f"Found {len(shipments)} shipments to poll")
        
        # Raggruppa spedizioni per id_carrier_api
        shipments_by_carrier: Dict[int, List[Row]] = {}
        for shipment in shipments:
            carrier_api_id = shipment.id_carrier_api
            if carrier_api_id not in shipments_by_carrier:
                shipments_by_carrier[carrier_api_id] = []
            shipments_by_carrier[carrier_api_id].append(shipment)
        
        logger.info(f"Grouped shipments into {len(shipments_by_carrier)} carrier groups")
        
        # Crea factory per ottenere tracking services
        carrier_repo = ApiCarrierRepository(db)
        factory = CarrierServiceFactory(carrier_repo)
        
        # Processa ogni gruppo di carrier
        for carrier_api_id, carrier_shipments in shipments_by_carrier.items():
            try:
                # Ottieni il carrier per determinare il tipo
                carrier = carrier_repo.get_by_id(carrier_api_id)
                if not carrier or not carrier.is_active:
                    logger.warning(f"Carrier API {carrier_api_id} not found or inactive, skipping")
                    continue
                
                carrier_type = carrier.carrier_type.value
                logger.info(f"Processing {len(carrier_shipments)} shipments for carrier {carrier_type} (API ID: {carrier_api_id})")
                
                # Ottieni il tracking service appropriato
                tracking_service = factory.get_tracking_service(carrier_api_id, db)
                
                # Filtra spedizioni in base a rate limiting e presenza eventi
                tracking_numbers_to_poll: List[str] = []
                has_events_count = 0
                no_events_count = 0
                
                for shipment in carrier_shipments:
                    tracking_number = shipment.tracking
                    if not tracking_number:
                        continue
                    
                    # Verifica rate limiting
                    if not _can_make_request(carrier_type, tracking_number):
                        logger.debug(f"Skipping {tracking_number} due to rate limiting")
                        continue
                    
                    # Verifica se ha eventi (per determinare intervallo polling)
                    has_events = shipping_repo.has_tracking_events(tracking_number)
                    if has_events:
                        has_events_count += 1
                    else:
                        no_events_count += 1
                    
                    tracking_numbers_to_poll.append(tracking_number)
                
                if not tracking_numbers_to_poll:
                    logger.info(f"No shipments to poll for carrier {carrier_type} (all rate limited)")
                    continue
                
                logger.info(
                    f"Polling {len(tracking_numbers_to_poll)} shipments for {carrier_type}: "
                    f"{no_events_count} without events, {has_events_count} with events"
                )
                
                # Chiama il tracking service
                try:
                    results = await tracking_service.get_tracking(tracking_numbers_to_poll, carrier_api_id)
                    
                    # Aggiorna stati spedizioni
                    updated_count = 0
                    for item in results:
                        tn = item.get("tracking_number")
                        state_id = item.get("current_internal_state_id")
                        if tn and isinstance(state_id, int):
                            try:
                                shipping_repo.update_state_by_tracking(tn, state_id)
                                updated_count += 1
                                # Aggiorna timestamp rate limiting
                                _update_rate_limit_timestamp(carrier_type, tn)
                            except Exception as e:
                                logger.warning(f"Error updating state for tracking {tn}: {str(e)}")
                    
                    logger.info(f"Updated {updated_count} shipment states for carrier {carrier_type}")
                    
                except Exception as e:
                    logger.error(f"Error polling tracking for carrier {carrier_type}: {str(e)}", exc_info=True)
                    # Continua con altri carrier anche in caso di errore
                    continue
                    
            except Exception as e:
                logger.error(f"Error processing carrier group {carrier_api_id}: {str(e)}", exc_info=True)
                # Continua con altri carrier anche in caso di errore
                continue
        
        # Pulizia rate limiting (rimuovi entry > 24h)
        _cleanup_rate_limit_cache()
        
        logger.info("Periodic tracking polling completed")
        
    except Exception as e:
        logger.error(f"Error in periodic tracking polling: {str(e)}", exc_info=True)


def _can_make_request(carrier_type: str, tracking_number: str) -> bool:
    """
    Verifica se è possibile fare una richiesta per questo tracking number
    rispettando il rate limiting.
    
    Args:
        carrier_type: Tipo di carrier (BRT, DHL, FEDEX)
        tracking_number: Numero di tracking
        
    Returns:
        True se può fare la richiesta, False altrimenti
    """
    if carrier_type not in CARRIER_POLLING_CONFIG:
        # Carrier sconosciuto, usa default
        rate_limit = DEFAULT_RATE_LIMIT_SECONDS
    else:
        config = CARRIER_POLLING_CONFIG[carrier_type]
        rate_limit = config.get("rate_limit", DEFAULT_RATE_LIMIT_SECONDS)
    
    # Inizializza dizionario per carrier se non esiste
    if carrier_type not in _last_tracking_request:
        _last_tracking_request[carrier_type] = {}
    
    last_request_time = _last_tracking_request[carrier_type].get(tracking_number, 0)
    current_time = time.time()
    
    return (current_time - last_request_time) >= rate_limit


def _update_rate_limit_timestamp(carrier_type: str, tracking_number: str) -> None:
    """
    Aggiorna il timestamp dell'ultima richiesta per questo tracking number.
    
    Args:
        carrier_type: Tipo di carrier
        tracking_number: Numero di tracking
    """
    if carrier_type not in _last_tracking_request:
        _last_tracking_request[carrier_type] = {}
    
    _last_tracking_request[carrier_type][tracking_number] = time.time()


def _cleanup_rate_limit_cache() -> None:
    """
    Rimuove entry dal cache di rate limiting più vecchie di 24 ore.
    """
    current_time = time.time()
    max_age = 24 * 3600  # 24 ore in secondi
    
    for carrier_type in list(_last_tracking_request.keys()):
        tracking_dict = _last_tracking_request[carrier_type]
        # Rimuovi entry vecchie
        keys_to_remove = [
            tn for tn, timestamp in tracking_dict.items()
            if (current_time - timestamp) > max_age
        ]
        for tn in keys_to_remove:
            del tracking_dict[tn]
        
        # Se il dizionario è vuoto, rimuovilo
        if not tracking_dict:
            del _last_tracking_request[carrier_type]


def _determine_polling_interval(
    db: Session,
    has_events_count: int,
    no_events_count: int,
    carrier_type: str
) -> int:
    """
    Determina l'intervallo di polling in base allo stato delle spedizioni.
    
    Args:
        db: Database session
        has_events_count: Numero di spedizioni con eventi
        no_events_count: Numero di spedizioni senza eventi
        carrier_type: Tipo di carrier
        
    Returns:
        Intervallo in secondi
    """
    if carrier_type not in CARRIER_POLLING_CONFIG:
        return DEFAULT_POLLING_INTERVAL
    
    config = CARRIER_POLLING_CONFIG[carrier_type]
    
    # Per BRT, usa intervalli dinamici
    if carrier_type == CarrierTypeEnum.BRT.value:
        # Se ci sono spedizioni senza eventi, usa intervallo iniziale
        if no_events_count > 0:
            return config["initial_interval"]
        else:
            return config["post_response_interval"]
    else:
        # Per altri carrier, usa intervallo fisso
        return config.get("interval", DEFAULT_POLLING_INTERVAL)


async def run_tracking_polling_task(db: Session):
    """
    Task periodica che gira in loop infinito, facendo polling del tracking.
    
    Usa intervalli dinamici basati sullo stato delle spedizioni:
    - BRT: 7.5 minuti se ci sono spedizioni senza eventi, 1.5 ore se tutte hanno eventi
    - Altri carrier: 1 ora (configurabile)
    
    Args:
        db: Database session (deve essere gestita correttamente per ogni iterazione)
    """
    logger.info("Starting tracking polling periodic task")
    
    while True:
        try:
            # Determina intervallo di polling
            # Per determinare l'intervallo, dobbiamo prima vedere lo stato delle spedizioni
            shipping_repo = ShippingRepository(db)
            shipments = shipping_repo.get_shipments_with_tracking(exclude_states=EXCLUDED_SHIPPING_STATES)
            
            if shipments:
                # Conta spedizioni con/senza eventi per ogni carrier
                carrier_repo = ApiCarrierRepository(db)
                has_events_by_carrier: Dict[str, int] = {}
                no_events_by_carrier: Dict[str, int] = {}
                
                for shipment in shipments:
                    carrier = carrier_repo.get_by_id(shipment.id_carrier_api)
                    if not carrier:
                        continue
                    
                    carrier_type = carrier.carrier_type.value
                    has_events = shipping_repo.has_tracking_events(shipment.tracking)
                    
                    if carrier_type not in has_events_by_carrier:
                        has_events_by_carrier[carrier_type] = 0
                        no_events_by_carrier[carrier_type] = 0
                    
                    if has_events:
                        has_events_by_carrier[carrier_type] += 1
                    else:
                        no_events_by_carrier[carrier_type] += 1
                
                # Determina intervallo minimo (più frequente)
                min_interval = DEFAULT_POLLING_INTERVAL
                for carrier_type in set(list(has_events_by_carrier.keys()) + list(no_events_by_carrier.keys())):
                    interval = _determine_polling_interval(
                        db,
                        has_events_by_carrier.get(carrier_type, 0),
                        no_events_by_carrier.get(carrier_type, 0),
                        carrier_type
                    )
                    min_interval = min(min_interval, interval)
                
                polling_interval = min_interval
            else:
                # Nessuna spedizione, usa intervallo default
                polling_interval = DEFAULT_POLLING_INTERVAL
            
            logger.info(f"Waiting {polling_interval} seconds ({polling_interval/60:.1f} minutes) before next tracking poll")
            await asyncio.sleep(polling_interval)
            
            # Esegui polling
            await poll_tracking_periodic(db)
            
        except Exception as e:
            logger.error(f"Error in tracking polling task: {str(e)}", exc_info=True)
            # In caso di errore, aspetta 5 minuti prima di riprovare
            await asyncio.sleep(300)
