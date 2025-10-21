"""
Platform Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Path, UploadFile, File, Form
from src.services.interfaces.platform_service_interface import IPlatformService
from src.repository.interfaces.platform_repository_interface import IPlatformRepository
from src.schemas.platform_schema import PlatformSchema, PlatformResponseSchema, AllPlatformsResponseSchema
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
    prefix="/api/v1/platforms",
    tags=["Platform"],
)

def get_platform_service(db: db_dependency) -> IPlatformService:
    """Dependency injection per Platform Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    platform_repo = configured_container.resolve_with_session(IPlatformRepository, db)
    platform_service = configured_container.resolve(IPlatformService)
    
    if hasattr(platform_service, '_platform_repository'):
        platform_service._platform_repository = platform_repo
    
    return platform_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllPlatformsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_platforms(
    user: dict = Depends(get_current_user),
    platform_service: IPlatformService = Depends(get_platform_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutte le platform con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    platforms = await platform_service.get_platforms(page=page, limit=limit)
    if not platforms:
        raise NotFoundException("Platforms", None)

    total_count = await platform_service.get_platforms_count()

    return {"platforms": platforms, "total": total_count, "page": page, "limit": limit}

@router.get("/{platform_id}", status_code=status.HTTP_200_OK, response_model=PlatformResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_platform_by_id(
    platform_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    platform_service: IPlatformService = Depends(get_platform_service)
):
    """
    Restituisce una singola platform basata sull'ID specificato.

    - **platform_id**: Identificativo della platform da ricercare.
    """
    platform = await platform_service.get_platform(platform_id)
    return platform

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Platform creata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_platform(
    platform_data: PlatformSchema,
    user: dict = Depends(get_current_user),
    platform_service: IPlatformService = Depends(get_platform_service)
):
    """
    Crea una nuova platform con i dati forniti.
    """
    return await platform_service.create_platform(platform_data)

@router.put("/{platform_id}", status_code=status.HTTP_200_OK, response_description="Platform aggiornata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_platform(
    platform_data: PlatformSchema,
    platform_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    platform_service: IPlatformService = Depends(get_platform_service)
):
    """
    Aggiorna i dati di una platform esistente basata sull'ID specificato.

    - **platform_id**: Identificativo della platform da aggiornare.
    """
    return await platform_service.update_platform(platform_id, platform_data)

@router.delete("/{platform_id}", status_code=status.HTTP_200_OK, response_description="Platform eliminata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_platform(
    platform_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    platform_service: IPlatformService = Depends(get_platform_service)
):
    """
    Elimina una platform basata sull'ID specificato.

    - **platform_id**: Identificativo della platform da eliminare.
    """
    await platform_service.delete_platform(platform_id)