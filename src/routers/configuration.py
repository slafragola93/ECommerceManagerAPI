"""
Configuration Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from src.services.interfaces.configuration_service_interface import IConfigurationService
from src.repository.interfaces.configuration_repository_interface import IConfigurationRepository
from src.schemas.configuration_schema import ConfigurationSchema, ConfigurationResponseSchema, AllConfigurationsResponseSchema
from src.core.container import container
from src.core.exceptions import (
    BaseApplicationException,
    ValidationException,
    NotFoundException,
    BusinessRuleException
)
from src.core.dependencies import db_dependency
from src.services.auth import authorize
from src.services.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/configurations",
    tags=["Configuration"]
)

def get_configuration_service(db: db_dependency) -> IConfigurationService:
    """Dependency injection per Configuration Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    configuration_repo = configured_container.resolve_with_session(IConfigurationRepository, db)
    
    # Crea il service con il repository
    configuration_service = configured_container.resolve(IConfigurationService)
    # Inietta il repository nel service
    if hasattr(configuration_service, '_configuration_repository'):
        configuration_service._configuration_repository = configuration_repo
    
    return configuration_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllConfigurationsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_configurations(
    user: dict = Depends(get_current_user),
    configuration_service: IConfigurationService = Depends(get_configuration_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i configuration con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    try:
        configurations = await configuration_service.get_configurations(page=page, limit=limit)
        if not configurations:
            raise HTTPException(status_code=404, detail="Nessun configuration trovato")

        total_count = await configuration_service.get_configurations_count()

        return {"configurations": configurations, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{configuration_id}", status_code=status.HTTP_200_OK, response_model=ConfigurationResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_configuration_by_id(
    user: dict = Depends(get_current_user),
    configuration_service: IConfigurationService = Depends(get_configuration_service),
    configuration_id: int = Path(gt=0)
):
    """
    Restituisce un singolo configuration basato sull'ID specificato.

    - **configuration_id**: Identificativo del configuration da ricercare.
    """
    try:
        configuration = await configuration_service.get_configuration(configuration_id)
        return configuration
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Configuration non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Configuration creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_configuration(
    configuration_data: ConfigurationSchema,
    user: dict = Depends(get_current_user),
    configuration_service: IConfigurationService = Depends(get_configuration_service)
):
    """
    Crea un nuovo configuration con i dati forniti.
    """
    try:
        return await configuration_service.create_configuration(configuration_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{configuration_id}", status_code=status.HTTP_200_OK, response_description="Configuration aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_configuration(
    configuration_data: ConfigurationSchema,
    user: dict = Depends(get_current_user),
    configuration_service: IConfigurationService = Depends(get_configuration_service),
    configuration_id: int = Path(gt=0)
):
    """
    Aggiorna i dati di un configuration esistente basato sull'ID specificato.

    - **configuration_id**: Identificativo del configuration da aggiornare.
    """
    try:
        return await configuration_service.update_configuration(configuration_id, configuration_data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Configuration non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{configuration_id}", status_code=status.HTTP_200_OK, response_description="Configuration eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_configuration(
    user: dict = Depends(get_current_user),
    configuration_service: IConfigurationService = Depends(get_configuration_service),
    configuration_id: int = Path(gt=0)
):
    """
    Elimina un configuration basato sull'ID specificato.

    - **configuration_id**: Identificativo del configuration da eliminare.
    """
    try:
        await configuration_service.delete_configuration(configuration_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Configuration non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
