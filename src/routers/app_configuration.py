"""
AppConfiguration Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from src.services.interfaces.app_configuration_service_interface import IAppConfigurationService
from src.repository.interfaces.app_configuration_repository_interface import IAppConfigurationRepository
from src.schemas.app_configuration_schema import AppConfigurationSchema, AppConfigurationResponseSchema, AllAppConfigurationsResponseSchema
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
    prefix="/api/v1/app_configurations",
    tags=["AppConfiguration"]
)

def get_app_configuration_service(db: db_dependency) -> IAppConfigurationService:
    """Dependency injection per AppConfiguration Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    app_configuration_repo = configured_container.resolve_with_session(IAppConfigurationRepository, db)
    
    # Crea il service con il repository
    app_configuration_service = configured_container.resolve(IAppConfigurationService)
    # Inietta il repository nel service
    if hasattr(app_configuration_service, '_app_configuration_repository'):
        app_configuration_service._app_configuration_repository = app_configuration_repo
    
    return app_configuration_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllAppConfigurationsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_app_configurations(
    user: dict = Depends(get_current_user),
    app_configuration_service: IAppConfigurationService = Depends(get_app_configuration_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i app_configuration con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    try:
        app_configurations = await app_configuration_service.get_app_configurations(page=page, limit=limit)
        if not app_configurations:
            raise HTTPException(status_code=404, detail="Nessun app_configuration trovato")

        total_count = await app_configuration_service.get_app_configurations_count()

        return {"configurations": app_configurations, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{app_configuration_id}", status_code=status.HTTP_200_OK, response_model=AppConfigurationResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_app_configuration_by_id(
    user: dict = Depends(get_current_user),
    app_configuration_service: IAppConfigurationService = Depends(get_app_configuration_service),
    app_configuration_id: int = Path(gt=0)
):
    """
    Restituisce un singolo app_configuration basato sull'ID specificato.

    - **app_configuration_id**: Identificativo del app_configuration da ricercare.
    """
    try:
        app_configuration = await app_configuration_service.get_app_configuration(app_configuration_id)
        return app_configuration
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="AppConfiguration non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="AppConfiguration creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_app_configuration(
    app_configuration_data: AppConfigurationSchema,
    app_configuration_service: IAppConfigurationService = Depends(get_app_configuration_service),
    user: dict = Depends(get_current_user)
):
    """
    Crea un nuovo app_configuration con i dati forniti.
    """
    try:
        return await app_configuration_service.create_app_configuration(app_configuration_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{app_configuration_id}", status_code=status.HTTP_200_OK, response_description="AppConfiguration aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_app_configuration(
    app_configuration_data: AppConfigurationSchema,
    app_configuration_service: IAppConfigurationService = Depends(get_app_configuration_service),
    app_configuration_id: int = Path(gt=0),
    user: dict = Depends(get_current_user)
):
    """
    Aggiorna i dati di un app_configuration esistente basato sull'ID specificato.

    - **app_configuration_id**: Identificativo del app_configuration da aggiornare.
    """
    try:
        return await app_configuration_service.update_app_configuration(app_configuration_id, app_configuration_data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="AppConfiguration non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{app_configuration_id}", status_code=status.HTTP_200_OK, response_description="AppConfiguration eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_app_configuration(
    user: dict = Depends(get_current_user),
    app_configuration_service: IAppConfigurationService = Depends(get_app_configuration_service),
    app_configuration_id: int = Path(gt=0)
):
    """
    Elimina un app_configuration basato sull'ID specificato.

    - **app_configuration_id**: Identificativo del app_configuration da eliminare.
    """
    try:
        await app_configuration_service.delete_app_configuration(app_configuration_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="AppConfiguration non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
