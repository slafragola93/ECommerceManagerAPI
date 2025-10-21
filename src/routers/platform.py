"""
Platform Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from src.services.interfaces.platform_service_interface import IPlatformService
from src.repository.interfaces.platform_repository_interface import IPlatformRepository
from src.schemas.platform_schema import PlatformSchema, PlatformResponseSchema, AllPlatformsResponseSchema
from src.core.container import container
from src.core.exceptions import (
    BaseApplicationException,
    ValidationException,
    NotFoundException,
    BusinessRuleException
)
from src.core.dependencies import db_dependency
from src.services.routers.auth_service import authorize
from src.services.core.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.routers.auth_service import get_current_user

router = APIRouter(
    prefix="/api/v1/platforms",
    tags=["Platform"]
)

def get_platform_service(db: db_dependency) -> IPlatformService:
    """Dependency injection per Platform Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    platform_repo = configured_container.resolve_with_session(IPlatformRepository, db)
    
    # Crea il service con il repository
    platform_service = configured_container.resolve(IPlatformService)
    # Inietta il repository nel service
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
    Restituisce tutti i platform con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    try:
        platforms = await platform_service.get_platforms(page=page, limit=limit)
        if not platforms:
            raise HTTPException(status_code=404, detail="Nessun platform trovato")

        total_count = await platform_service.get_platforms_count()

        return {"platforms": platforms, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{platform_id}", status_code=status.HTTP_200_OK, response_model=PlatformResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_platform_by_id(
    user: dict = Depends(get_current_user),
    platform_service: IPlatformService = Depends(get_platform_service),
    platform_id: int = Path(gt=0)
):
    """
    Restituisce un singolo platform basato sull'ID specificato.

    - **platform_id**: Identificativo del platform da ricercare.
    """
    try:
        platform = await platform_service.get_platform(platform_id)
        return platform
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Platform non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Platform creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_platform(
    platform_data: PlatformSchema,
    platform_service: IPlatformService = Depends(get_platform_service),
    user: dict = Depends(get_current_user)
):
    """
    Crea un nuovo platform con i dati forniti.
    """
    try:
        return await platform_service.create_platform(platform_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{platform_id}", status_code=status.HTTP_200_OK, response_description="Platform aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_platform(
    platform_data: PlatformSchema,
    platform_service: IPlatformService = Depends(get_platform_service),
    platform_id: int = Path(gt=0),
    user: dict = Depends(get_current_user)
):
    """
    Aggiorna i dati di un platform esistente basato sull'ID specificato.

    - **platform_id**: Identificativo del platform da aggiornare.
    """
    try:
        return await platform_service.update_platform(platform_id, platform_data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Platform non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{platform_id}", status_code=status.HTTP_200_OK, response_description="Platform eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_platform(
    user: dict = Depends(get_current_user),
    platform_service: IPlatformService = Depends(get_platform_service),
    platform_id: int = Path(gt=0)
):
    """
    Elimina un platform basato sull'ID specificato.

    - **platform_id**: Identificativo del platform da eliminare.
    """
    try:
        await platform_service.delete_platform(platform_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Platform non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
