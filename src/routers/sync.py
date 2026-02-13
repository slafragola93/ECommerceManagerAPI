"""
Synchronization endpoints for e-commerce platforms
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Path, Body
from starlette import status
from sqlalchemy.orm import Session
from typing import Dict, Any
import asyncio
import logging

from src.database import get_db
from src.services.routers.auth_service import db_dependency, get_current_user
from src.services.core.wrap import check_authentication
from src.services.routers.auth_service import authorize
from src.repository.platform_repository import PlatformRepository
from src.repository.store_repository import StoreRepository
from src.repository.product_repository import ProductRepository
from src.repository.order_repository import OrderRepository
from src.routers.dependencies import get_ecommerce_service
from src.services.routers.order_service import OrderService
from src.services.interfaces.order_service_interface import IOrderService
from src.schemas.order_schema import OrderStateSyncSchema, OrderStateSyncResponseSchema
from src.schemas.product_schema import SyncImagesResponseSchema
import time

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix='/api/v1/sync',
    tags=['Synchronization'],
)


def get_platform_repository(db: db_dependency) -> PlatformRepository:
    return PlatformRepository(db)


def get_store_repository(db: db_dependency) -> StoreRepository:
    return StoreRepository(db)


def get_order_service(db: Session = Depends(get_db)) -> IOrderService:
    """Dependency injection per Order Service."""
    order_repo = OrderRepository(db)
    return OrderService(order_repo)

def get_default_store(sr: StoreRepository = Depends(get_store_repository)):
    """
    Dependency per recuperare lo store di default (is_default = 1)
    
    Raises:
        HTTPException 400: Se non viene trovato nessuno store di default
    
    Returns:
        Store: Lo store di default
    """
    store = sr.get_default()
    
    if not store:
        raise HTTPException(
            status_code=400, 
            detail="No default store found (is_default = 1). Please set a default store."
        )
    
    return store


@router.post("/prestashop", status_code=status.HTTP_202_ACCEPTED)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def sync_prestashop(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    store_repo: StoreRepository = Depends(get_store_repository),
    store_id: int = Query(..., description="ID dello store da sincronizzare"),  
    limit: int = None,
    user: dict = Depends(get_current_user)
):
    """
    Start PrestaShop incremental synchronization process
    
    This endpoint starts an asynchronous synchronization process that will:
    1. Retrieve the store by ID
    2. Sync all data in the correct order (base tables first, then dependent tables)
    3. Process data in batches to avoid timeouts
    4. Log all operations for tracking
    
    Returns:
        202 Accepted: Synchronization started successfully
        400 Bad Request: Missing configuration or invalid store
        500 Internal Server Error: Failed to start synchronization
    """
    # Verifica che lo store esista
    store = store_repo.get_by_id(store_id)
    
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")
    
    # Start background synchronization
    background_tasks.add_task(
        _run_prestashop_sync,
        db=db,
        store_id=store_id,
        new_elements=True,
        limit=limit
    )
    
    return {
        "message": "PrestaShop incremental synchronization started",
        "status": "accepted",
        "sync_type": "incremental",
        "store_id": store_id,
        "store_name": store.name,
        "vat_number": store.get_default_vat_number(),
        "sync_id": f"prestashop_incremental_{user['id']}_{int(__import__('time').time())}"
    }
        

@router.post("/prestashop/full", status_code=status.HTTP_202_ACCEPTED)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def sync_prestashop_full(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    store_id: int = Query(..., description="ID dello store da sincronizzare"),
    user: dict = Depends(get_current_user)
):
    """
    Start PrestaShop full synchronization process
    
    This endpoint starts an asynchronous synchronization process that will:
    1. Retrieve the store by ID
    2. Sync all data in the correct order (base tables first, then dependent tables)
    3. Process data in batches to avoid timeouts
    4. Log all operations for tracking
    
    Returns:
        202 Accepted: Synchronization started successfully
        400 Bad Request: Missing configuration or invalid store
        500 Internal Server Error: Failed to start synchronization
    """
    # Verifica che lo store esista
    store_repo = StoreRepository(db)
    store = store_repo.get_by_id(store_id)
    
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")
    
    # Start background synchronization
    background_tasks.add_task(
        _run_prestashop_sync,
        db=db,
        store_id=store_id,
        new_elements=False
    )
    
    return {
        "message": "PrestaShop full synchronization started",
        "status": "accepted",
        "sync_type": "full",
        "store_id": store_id,
        "store_name": store.name,
        "vat_number": store.get_default_vat_number(),
        "sync_id": f"prestashop_full_{user['id']}_{int(__import__('time').time())}"
    }


@router.get("/prestashop/status", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_prestashop_sync_status(
    user: dict = Depends(get_current_user),
    sync_id: str = None
):
    """
    Get PrestaShop synchronization status
    
    Args:
        sync_id: Optional sync ID to get specific status
        
    Returns:
        Current synchronization status and progress
    """
    # TODO: Implement status tracking
    # For now, return a placeholder response
    return {
        "status": "not_implemented",
        "message": "Status tracking will be implemented in the next phase",
        "sync_id": sync_id
    }


@router.get("/prestashop/last-ids", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_prestashop_last_imported_ids(
    db: Session = Depends(get_db),
    store_id: int = Query(..., description="ID dello store"),
    user: dict = Depends(get_current_user)
):
    """
    Get the last imported ID origin for each table
    
    This endpoint shows the last imported ID for each table, which is useful for:
    - Understanding what data has been imported
    - Planning incremental synchronizations
    - Debugging sync issues
    
    Returns:
        Dict with table names and their last imported ID origins
    """
    # Verifica che lo store esista
    store_repo = StoreRepository(db)
    store = store_repo.get_by_id(store_id)
    
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")
    
    service_class = get_ecommerce_service(store_id, db)
    async with service_class as ps_service:
        last_ids = await ps_service._get_last_imported_ids()
        
        return {
            "last_imported_ids": last_ids,
            "store_id": store_id,
            "store_name": store.name,
            "message": "Last imported IDs retrieved successfully",
            "note": "These IDs represent the highest ID origin imported for each table"
        }


@router.post("/sync-images", status_code=status.HTTP_200_OK, response_model=SyncImagesResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def sync_images(
    db: Session = Depends(get_db),
    store_repo: StoreRepository = Depends(get_store_repository),
    id_store: int = Query(..., description="ID dello store per la sincronizzazione immagini prodotti"),
    user: dict = Depends(get_current_user)
):
    """
    Sincronizza le immagini dei prodotti per lo store indicato.

    Recupera il service e-commerce associato allo store (es. PrestaShop), carica i prodotti
    dal database e dall'API della piattaforma, e scarica/aggiorna le immagini (inclusi
    prodotti senza immagine, per i quali viene impostato il fallback).

    Returns:
        200 OK: Riepilogo con id_store, products_processed e message.
        400 Bad Request: Store non trovato o piattaforma non supportata.
    """
    store = store_repo.get_by_id(id_store)
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {id_store} not found")

    ecommerce_service = get_ecommerce_service(store_id=id_store, db=db)
    async with ecommerce_service:
        result = await ecommerce_service.sync_product_images_standalone()

    return SyncImagesResponseSchema(
        id_store=id_store,
        success=True,
        products_processed=result.get("products_processed", 0),
        message=result.get("message", "Image sync completed."),
    )


async def _run_prestashop_sync(db: Session, store_id: int, new_elements: bool = True, incremental: bool = None, limit: int = None):
    """
    Background task to run PrestaShop synchronization
    
    Args:
        db: Database session
        store_id: Store ID in the stores table
        new_elements: Whether to sync only new elements (incremental sync)
        incremental: Whether to run incremental sync (only new data) - deprecated, use new_elements
        limit: Maximum number of records to process per batch
    """
    # Handle both new_elements and incremental parameters
    if incremental is not None:
        new_elements = incremental
    
    sync_type = "incremental" if new_elements else "full"
    
    # Recupera lo store per verificare che esista
    store_repo = StoreRepository(db)
    store = store_repo.get_by_id(store_id)
    
    if not store:
        raise Exception(f"Store with ID {store_id} not found")
    
    if not store.is_active:
        raise Exception(f"Store {store.name} is not active")
    
    # Note: limit parameter is not currently supported by PrestaShopService
    # but we log it for future implementation
    if limit:
        print(f"Limit parameter set to {limit} (not yet implemented in PrestaShopService)")
    
    # Crea il service usando la funzione centralizzata
    service_class = get_ecommerce_service(store_id, db, new_elements=new_elements)
    
    async with service_class as ps_service:
        print(f"Base URL: {ps_service.base_url}")
        print(f"API Key: {ps_service.api_key[:10]}...")
        # Run synchronization based on type
        results = await ps_service.sync_all_data()
        
        # Sincronizza anche gli stati ordini
        try:
            print("Syncing order states...")
            order_states = await ps_service.sync_order_states()
            print(f"Order states sync completed: {len(order_states)} states retrieved")
        except Exception as e:
            print(f"Warning: Order states sync failed: {str(e)}")
            # Non bloccare la sincronizzazione per errori di sync stati
        
        print(f"{sync_type.capitalize()} synchronization completed:")
        print(f"  Total processed: {results['total_processed']}")
        print(f"  Total errors: {results['total_errors']}")
        print(f"  Status: {results['status']}")
        
        if new_elements and 'last_ids' in results:
            print(f"  Last imported IDs: {results['last_ids']}")
        
        # Log detailed results
        for phase in results['phases']:
            print(f"  Phase: {phase['phase']}")
            print(f"    Processed: {phase['total_processed']}")
            print(f"    Errors: {phase['total_errors']}")
            
            for func_result in phase['functions']:
                status_icon = "✅" if func_result['status'] == 'SUCCESS' else "❌"
                print(f"    {status_icon} {func_result['function']}: {func_result['processed']} records")
                if func_result['status'] == 'ERROR':
                    print(f"      Error: {func_result['error']}")
        

@router.post("/test-connection", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def test_prestashop_connection(
    db: Session = Depends(get_db),
    store_id: int = Query(..., description="ID dello store da testare"),
    user: dict = Depends(get_current_user)
):
    """
    Test PrestaShop API connection
    
    This endpoint tests the connection to PrestaShop API using the store configuration.
    Useful for verifying configuration before starting a full synchronization.
    
    Returns:
        200 OK: Connection successful
        400 Bad Request: Missing configuration
        401 Unauthorized: Invalid credentials
        500 Internal Server Error: Connection failed
    """
    # Verifica che lo store esista
    store_repo = StoreRepository(db)
    store = store_repo.get_by_id(store_id)
    
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")
    
    # Test connection
    service_class = get_ecommerce_service(store_id, db)
    async with service_class as ps_service:
        # Try to get a simple endpoint (languages)
        response = await ps_service._make_request('/api/languages')
        
        return {
            "status": "success",
            "message": "PrestaShop connection successful",
            "store_id": store_id,
            "store_name": store.name,
            "base_url": ps_service.base_url,
            "api_key_preview": f"{ps_service.api_key[:10]}..." if len(ps_service.api_key) > 10 else "***",
            "test_endpoint": "/api/languages",
            "response_keys": list(response.keys()) if response else [],
            "response_sample": str(response)[:500] if response else "No response"
        }


@router.post("/products/quantity", status_code=status.HTTP_202_ACCEPTED)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def sync_products_quantity(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    store_id: int = Query(..., description="ID dello store da sincronizzare"),
    user: dict = Depends(get_current_user)
):
    """
    Sincronizza le quantità dei prodotti dalla piattaforma e-commerce.
    
    Questo endpoint avvia un processo asincrono che:
    1. Seleziona il service corretto per lo store
    2. Chiama l'API della piattaforma per recuperare le quantità aggiornate
    3. Aggiorna i prodotti nel database con le nuove quantità
    
    Returns:
        202 Accepted: Sincronizzazione quantità avviata con successo
        400 Bad Request: Store non supportato o configurazione mancante
        500 Internal Server Error: Errore nell'avvio della sincronizzazione
    """
    # Verifica che lo store esista
    store_repo = StoreRepository(db)
    store = store_repo.get_by_id(store_id)
    
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")
    
    background_tasks.add_task(
        _run_quantity_sync,
        db=db,
        store_id=store_id,
        store_name=store.name
    )
    
    return {
        "message": "Product quantity synchronization started",
        "status": "accepted",
        "store_id": store_id,
        "store_name": store.name,
        "sync_id": f"quantity_sync_{user['id']}_{int(time.time())}"
    }


async def _run_quantity_sync(db: Session, store_id: int, store_name: str):
    """
    Background task per eseguire la sincronizzazione delle quantità dei prodotti.
    
    Args:
        db: Database session
        store_id: ID dello store
        store_name: Nome dello store
    """
    print(f"🚀 Starting quantity synchronization for store: {store_name} (ID: {store_id})")
    
    try:
        # Recupera lo store per verificare che esista
        store_repo = StoreRepository(db)
        store = store_repo.get_by_id(store_id)
        
        if not store:
            raise Exception(f"Store with ID {store_id} not found")
        
        # Seleziona il service corretto per lo store
        service_class = get_ecommerce_service(store_id, db)
        
        # Crea il repository per i prodotti
        product_repo = ProductRepository(db)
        
        # Esegui la sincronizzazione usando async context manager
        async with service_class as service:
            print(f"📡 Fetching quantities from {store_name} API...")
            
            # Chiama sync_quantity del service
            sync_result = await service.sync_quantity()
            
            quantity_map = sync_result.get('quantity_map', {})
            total_items = sync_result.get('total_items', 0)
            stats = sync_result.get('stats', {})
            
            print(f"✅ Retrieved {total_items} product quantities from API")
            
            if not quantity_map:
                print("⚠️ No quantities to update")
                return
            
            # Aggiorna le quantità nel database
            print(f"💾 Updating quantities in database for store {store_id}...")
            updated_count = product_repo.bulk_update_quantity(
                quantity_map=quantity_map,
                id_store=store_id
            )
            
            print(f"✅ Quantity synchronization completed:")
            print(f"   - Retrieved: {total_items} items")
            print(f"   - Updated: {updated_count} products")
            if stats.get('errors'):
                print(f"   - Errors: {len(stats.get('errors', []))}")
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        error_msg = f"Error in quantity synchronization: {str(e)}"
        print(f"❌ {error_msg}")
        raise


@router.post("/products/price", status_code=status.HTTP_202_ACCEPTED)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def sync_products_price(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    store_id: int = Query(..., description="ID dello store da sincronizzare"),
    user: dict = Depends(get_current_user)
):
    """
    Sincronizza i prezzi dei prodotti dalla piattaforma e-commerce.
    
    Questo endpoint avvia un processo asincrono che:
    1. Seleziona il service corretto in base alla piattaforma (PrestaShop, etc.)
    2. Chiama l'API della piattaforma per recuperare i prezzi aggiornati (price)
    3. Aggiorna i prodotti nel database con i nuovi prezzi (price)
    
    Returns:
        202 Accepted: Sincronizzazione prezzi avviata con successo
        400 Bad Request: Piattaforma non supportata o configurazione mancante
        500 Internal Server Error: Errore nell'avvio della sincronizzazione
    """
    # Verifica che lo store esista
    store_repo = StoreRepository(db)
    store = store_repo.get_by_id(store_id)
    
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")
    
    background_tasks.add_task(
        _run_price_sync,
        db=db,
        store_id=store_id,
        store_name=store.name
    )
    
    return {
        "message": "Product price synchronization started",
        "status": "accepted",
        "store_id": store_id,
        "store_name": store.name,
        "sync_id": f"price_sync_{user['id']}_{int(time.time())}"
    }


async def _run_price_sync(db: Session, store_id: int, store_name: str):
    """
    Background task per eseguire la sincronizzazione dei prezzi dei prodotti.
    
    Args:
        db: Database session
        store_id: ID dello store
        store_name: Nome dello store
    """
    print(f"🚀 Starting price synchronization for store: {store_name} (ID: {store_id})")
    
    try:
        # Recupera lo store per verificare che esista
        store_repo = StoreRepository(db)
        store = store_repo.get_by_id(store_id)
        
        if not store:
            raise Exception(f"Store with ID {store_id} not found")
        
        # Seleziona il service corretto per lo store
        service_class = get_ecommerce_service(store_id, db)
        
        # Crea il repository per i prodotti
        product_repo = ProductRepository(db)
        
        # Esegui la sincronizzazione usando async context manager
        async with service_class as service:
            print(f"📡 Fetching prices from {store_name} API...")
            
            # Chiama sync_price del service
            sync_result = await service.sync_price()
            
            price_map = sync_result.get('price_map', {})
            total_items = sync_result.get('total_items', 0)
            stats = sync_result.get('stats', {})
            
            print(f"✅ Retrieved {total_items} product prices from API")
            
            if not price_map:
                print("⚠️ No prices to update")
                return
            
            # Aggiorna i prezzi nel database
            print(f"💾 Updating prices in database for store {store_id}...")
            updated_count = product_repo.bulk_update_price(
                price_map=price_map,
                id_store=store_id
            )
            
            print(f"✅ Price synchronization completed:")
            print(f"   - Retrieved: {total_items} items")
            print(f"   - Updated: {updated_count} products")
            if stats.get('errors'):
                print(f"   - Errors: {len(stats.get('errors', []))}")
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        error_msg = f"Error in price synchronization: {str(e)}"
        print(f"❌ {error_msg}")
        raise


@router.post("/products/details", status_code=status.HTTP_202_ACCEPTED)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def sync_products_details(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    store_id: int = Query(..., description="ID dello store da sincronizzare"),
    user: dict = Depends(get_current_user)
):
    """
    Sincronizza i dettagli dei prodotti dalla piattaforma e-commerce.
    
    Questo endpoint avvia un processo asincrono che:
    1. Recupera dettagli prodotti (SKU, REFERENCE, WEIGHT, DEPTH, HEIGHT, WIDTH, 
       PURCHASE_PRICE, MINIMAL_QUANTITY, PRICE_WITHOUT_TAX) dall'API della piattaforma
    2. Recupera quantità prodotti usando sync_quantity esistente
    3. Unisce i dati e aggiorna i prodotti nel database con bulk update
    
    Returns:
        202 Accepted: Sincronizzazione dettagli prodotti avviata con successo
        400 Bad Request: Store non supportato o configurazione mancante
        500 Internal Server Error: Errore nell'avvio della sincronizzazione
    """
    # Verifica che lo store esista
    store_repo = StoreRepository(db)
    store = store_repo.get_by_id(store_id)
    
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")
    
    background_tasks.add_task(
        _run_details_sync,
        db=db,
        store_id=store_id,
        store_name=store.name
    )
    
    return {
        "message": "Product details synchronization started",
        "status": "accepted",
        "store_id": store_id,
        "store_name": store.name,
        "sync_id": f"details_sync_{user['id']}_{int(time.time())}"
    }


async def _run_details_sync(db: Session, store_id: int, store_name: str):
    """
    Background task per eseguire la sincronizzazione dei dettagli dei prodotti.
    
    Recupera dettagli prodotti e quantità in parallelo, li unisce e aggiorna il database.
    
    Args:
        db: Database session
        store_id: ID dello store
        store_name: Nome dello store
    """
    print(f"🚀 Starting product details synchronization for store: {store_name} (ID: {store_id})")
    
    try:
        # Recupera lo store per verificare che esista
        store_repo = StoreRepository(db)
        store = store_repo.get_by_id(store_id)
        
        if not store:
            raise Exception(f"Store with ID {store_id} not found")
        
        # Seleziona il service corretto per lo store
        service_class = get_ecommerce_service(store_id, db)
        
        # Crea il repository per i prodotti
        product_repo = ProductRepository(db)
        
        # Esegui la sincronizzazione usando async context manager
        async with service_class as service:
            print(f"📡 Fetching product details and quantities from {store_name} API...")
            
            # Ottimizzazione: chiama sync_product_details() e sync_quantity() in parallelo
            details_result, quantity_result = await asyncio.gather(
                service.sync_product_details(),
                service.sync_quantity(),
                return_exceptions=True
            )
            
            # Gestisci eccezioni dai risultati paralleli
            if isinstance(details_result, Exception):
                raise details_result
            if isinstance(quantity_result, Exception):
                raise quantity_result
            
            details_map = details_result.get('details_map', {})
            quantity_map = quantity_result.get('quantity_map', {})
            total_items = details_result.get('total_items', 0)
            stats_details = details_result.get('stats', {})
            stats_quantity = quantity_result.get('stats', {})
            
            print(f"✅ Retrieved {total_items} product details from API")
            print(f"✅ Retrieved {len(quantity_map)} product quantities from API")
            
            if not details_map:
                print("⚠️ No product details to update")
                return
            
            # Unisce i due dict: aggiungi quantity a details_map
            # Filtra id_origin = 0 (già fatto in sync_product_details, ma doppio check)
            print(f"🔗 Merging details and quantities...")
            for id_origin in list(details_map.keys()):
                if id_origin > 0:  # SKIP id_origin = 0 (double check)
                    details_map[id_origin]['quantity'] = quantity_map.get(id_origin, 0)
                else:
                    # Rimuovi se id_origin = 0 (non dovrebbe accadere, ma sicurezza)
                    details_map.pop(id_origin, None)
            
            # Filtra finale per rimuovere eventuali id_origin = 0 rimasti
            details_map = {k: v for k, v in details_map.items() if k > 0}
            
            print(f"✅ Merged {len(details_map)} products with details and quantities")
            
            # Aggiorna i dettagli nel database
            print(f"💾 Updating product details in database for store {store_id}...")
            updated_count = product_repo.bulk_update_product_details(
                details_map=details_map,
                id_store=store_id
            )
            
            print(f"✅ Product details synchronization completed:")
            print(f"   - Retrieved: {total_items} items")
            print(f"   - Updated: {updated_count} products")
            if stats_details.get('errors'):
                print(f"   - Details errors: {len(stats_details.get('errors', []))}")
            if stats_quantity.get('errors'):
                print(f"   - Quantity errors: {len(stats_quantity.get('errors', []))}")
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        error_msg = f"Error in product details synchronization: {str(e)}"
        print(f"❌ {error_msg}")
        raise


@router.post("/orders/{order_id}/sync-state",
             status_code=status.HTTP_200_OK,
             summary="Sincronizza stato ordine con ecommerce",
             description="Sincronizza lo stato di un ordine sia localmente (order.id_ecommerce_state) che sulla piattaforma ecommerce remota (PrestaShop, Magento, ecc.)",
             response_description="Risultato della sincronizzazione",
             response_model=OrderStateSyncResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['U'])
async def sync_order_state_to_ecommerce(
    order_id: int = Path(..., gt=0, description="ID dell'ordine da sincronizzare"),
    sync_data: OrderStateSyncSchema = Body(..., description="Dati di sincronizzazione"),
    user: dict = Depends(get_current_user),
    order_service: IOrderService = Depends(get_order_service)
):
    """
    Sincronizza lo stato di un ordine con la piattaforma ecommerce remota.
    
    **Flusso:**
    1. Recupera l'ordine tramite OrderRepository
    2. Verifica che l'ordine abbia id_store e id_platform != 0
    3. Cerca EcommerceOrderState con id_ecommerce_order_state e id_store
    4. Estrae id_platform_state da EcommerceOrderState
    5. Crea il service ecommerce appropriato (PrestaShopService, MagentoService, ecc.)
    6. Sincronizza lo stato con la piattaforma remota usando id_platform_state
    7. Se successo, aggiorna order.id_ecommerce_state localmente usando id_ecommerce_order_state
    
    **Validazioni:**
    - order_id > 0
    - id_ecommerce_order_state > 0
    - Ordine deve avere id_store valido
    - Ordine deve avere id_platform != 0
    - EcommerceOrderState deve esistere per id_ecommerce_order_state + id_store
    
    **Errori:**
    - 404: Ordine non trovato o EcommerceOrderState non trovato
    - 400: Ordine senza id_store, id_platform == 0, o service ecommerce non supportato
    - 500: Errore durante sincronizzazione con piattaforma
    """
    return await order_service.sync_order_state_to_ecommerce(
        order_id=order_id,
        id_ecommerce_order_state=sync_data.id_ecommerce_order_state
    )
         