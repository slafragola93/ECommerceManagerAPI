"""
Servizio per sincronizzazione periodica degli stati ordini da e-commerce
"""
import asyncio
import logging
from typing import List
from sqlalchemy.orm import Session

from src.repository.store_repository import StoreRepository
from src.services.ecommerce.service_factory import create_ecommerce_service
from src.services.ecommerce.prestashop_service import PrestaShopOrderState

logger = logging.getLogger(__name__)


async def sync_order_states_periodic(db: Session):
    """
    Task periodica per sincronizzare stati ordini da tutti gli store attivi.
    
    Questa funzione:
    1. Recupera tutti gli store attivi
    2. Per ogni store, usa create_ecommerce_service per ottenere il service corretto
    3. Chiama sync_order_states() del service
    4. Verifica se stati esistono già in order_states locale
    5. Crea/aggiorna stati locali se necessario
    
    Args:
        db: Database session
    """
    try:
        logger.info("Starting periodic order states synchronization")
        
        # Recupera tutti gli store attivi
        store_repo = StoreRepository(db)
        active_stores = store_repo.get_active_stores()
        
        if not active_stores:
            logger.info("No active stores found, skipping order states sync")
            return
        
        logger.info(f"Found {len(active_stores)} active stores")
        
        # Per ogni store, sincronizza gli stati
        for store in active_stores:
            try:
                logger.info(f"Syncing order states for store {store.id_store} ({store.name})")
                
                # Usa factory per ottenere il service corretto
                ecommerce_service = create_ecommerce_service(store.id_store, db)
                
                # Usa async context manager per inizializzare il service
                async with ecommerce_service:
                    # Chiama sync_order_states() del service
                    order_states = await ecommerce_service.sync_order_states()
                    
                    if not order_states:
                        logger.warning(f"No order states retrieved for store {store.id_store}")
                        continue
                    
                    logger.info(f"Retrieved {len(order_states)} order states from store {store.id_store}")
                    
                    # Verifica e aggiorna stati locali
                    await _update_local_order_states(db, order_states, store.id_store)
                    
            except Exception as e:
                logger.error(f"Error syncing order states for store {store.id_store}: {str(e)}", exc_info=True)
                # Continua con il prossimo store anche in caso di errore
                continue
        
        logger.info("Periodic order states synchronization completed")
        
    except Exception as e:
        logger.error(f"Error in periodic order states synchronization: {str(e)}", exc_info=True)


async def _update_local_order_states(db: Session, order_states: List[PrestaShopOrderState], store_id: int):
    """
    Aggiorna gli stati ordini locali con quelli recuperati dall'e-commerce.
    
    Args:
        db: Database session
        order_states: Lista di stati ordini recuperati dall'e-commerce
        store_id: ID dello store
    """
    try:
        from src.models.ecommerce_order_state import EcommerceOrderState
        from src.repository.store_repository import StoreRepository
        from sqlalchemy.sql import func
        
        store_repo = StoreRepository(db)
        store = store_repo.get_by_id(store_id)
        
        if not store or not store.platform:
            logger.warning(f"Store {store_id} non trovato o senza piattaforma")
            return
        
        platform_name = store.platform.name
        
        for state in order_states:
            try:
                # Cerca se lo stato esiste già per questo store e platform_state_id
                existing_state = db.query(EcommerceOrderState).filter(
                    EcommerceOrderState.id_store == store_id,
                    EcommerceOrderState.id_platform_state == state.id
                ).first()
                
                if existing_state:
                    # Aggiorna nome se cambiato
                    if existing_state.name != state.name:
                        existing_state.name = state.name
                        existing_state.updated_at = func.now()
                        logger.debug(f"Updated ecommerce order state {state.id} for store {store_id}: {state.name}")
                else:
                    # Crea nuovo stato
                    new_state = EcommerceOrderState(
                        id_store=store_id,
                        id_platform_state=state.id,
                        name=state.name,
                        platform_name=platform_name
                    )
                    db.add(new_state)
                    logger.info(f"Created ecommerce order state {state.id} ({state.name}) for store {store_id}")
                
            except Exception as e:
                logger.warning(f"Error processing order state {state.id}: {str(e)}")
                continue
        
        db.commit()
        logger.info(f"Successfully synced {len(order_states)} order states for store {store_id}")
                
    except Exception as e:
        logger.error(f"Error updating local order states: {str(e)}", exc_info=True)
        db.rollback()


async def run_order_states_sync_task(db: Session):
    """
    Task che gira in loop infinito, sincronizzando stati ordini ogni ora.
    
    Args:
        db: Database session (deve essere gestita correttamente per ogni iterazione)
    """
    logger.info("Starting order states sync periodic task (will sync every hour)")
    
    while True:
        try:
            # Attendi 1 ora (3600 secondi) prima di eseguire la sincronizzazione
            logger.info("Waiting 1 hour before next order states sync")
            await asyncio.sleep(3600)
            
            # Sincronizza stati ordini
            await sync_order_states_periodic(db)
            
        except Exception as e:
            logger.error(f"Error in order states sync task: {str(e)}", exc_info=True)
            # In caso di errore, aspetta 5 minuti prima di riprovare
            await asyncio.sleep(300)

