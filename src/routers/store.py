"""
Store Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Path
from src.services.interfaces.store_service_interface import IStoreService
from src.repository.interfaces.store_repository_interface import IStoreRepository
from src.repository.interfaces.platform_repository_interface import IPlatformRepository
from src.schemas.store_schema import (
    StoreCreateSchema, 
    StoreUpdateSchema, 
    StoreResponseSchema, 
    AllStoresResponseSchema
)
from src.core.container import container
from src.core.exceptions import (
    NotFoundException
)
from src.core.dependencies import db_dependency
from src.services.routers.auth_service import authorize
from src.services.core.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.routers.auth_service import get_current_user

router = APIRouter(
    prefix="/api/v1/stores",
    tags=["Store"],
)

def get_store_service(db: db_dependency) -> IStoreService:
    """Dependency injection per Store Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    store_repo = configured_container.resolve_with_session(IStoreRepository, db)
    platform_repo = configured_container.resolve_with_session(IPlatformRepository, db)
    store_service = configured_container.resolve(IStoreService)
    
    if hasattr(store_service, '_store_repository'):
        store_service._store_repository = store_repo
    if hasattr(store_service, '_platform_repository'):
        store_service._platform_repository = platform_repo
    
    return store_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllStoresResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_stores(
    user: dict = Depends(get_current_user),
    store_service: IStoreService = Depends(get_store_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti gli store con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    stores = await store_service.get_stores(page=page, limit=limit)
    if not stores:
        raise NotFoundException("Stores", None)

    total_count = await store_service.get_stores_count()

    return {"stores": stores, "total": total_count, "page": page, "limit": limit}

@router.get("/default", status_code=status.HTTP_200_OK, response_model=StoreResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_default_store(
    user: dict = Depends(get_current_user),
    store_service: IStoreService = Depends(get_store_service)
):
    """
    Restituisce lo store di default.
    """
    store = await store_service.get_default_store()
    return store

@router.get("/{store_id}", status_code=status.HTTP_200_OK, response_model=StoreResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_store_by_id(
    store_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    store_service: IStoreService = Depends(get_store_service)
):
    """
    Restituisce un singolo store basato sull'ID specificato.

    - **store_id**: Identificativo dello store da ricercare.
    """
    store = await store_service.get_store(store_id)
    return store

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Store creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_store(
    store_data: StoreCreateSchema,
    user: dict = Depends(get_current_user),
    store_service: IStoreService = Depends(get_store_service)
):
    """
    Crea un nuovo store con i dati forniti.
    """
    return await store_service.create_store(store_data)

@router.put("/{store_id}", status_code=status.HTTP_200_OK, response_description="Store aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_store(
    store_data: StoreUpdateSchema,
    store_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    store_service: IStoreService = Depends(get_store_service)
):
    """
    Aggiorna i dati di uno store esistente basato sull'ID specificato.

    - **store_id**: Identificativo dello store da aggiornare.
    """
    return await store_service.update_store(store_id, store_data)

@router.delete("/{store_id}", status_code=status.HTTP_200_OK, response_description="Store eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_store(
    store_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    store_service: IStoreService = Depends(get_store_service)
):
    """
    Elimina uno store basato sull'ID specificato.

    - **store_id**: Identificativo dello store da eliminare.
    """
    await store_service.delete_store(store_id)

