"""
Configuration Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Path, UploadFile, File, Form
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
from src.services.routers.auth_service import authorize
from src.services.core.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.routers.auth_service import get_current_user

router = APIRouter(
    prefix="/api/v1/configurations",
    tags=["Configuration"],
)

def get_configuration_service(db: db_dependency) -> IConfigurationService:
    """Dependency injection per Configuration Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    configuration_repo = configured_container.resolve_with_session(IConfigurationRepository, db)
    configuration_service = configured_container.resolve(IConfigurationService)
    
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
    Restituisce tutte le configuration con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    configurations = await configuration_service.get_configurations(page=page, limit=limit)
    if not configurations:
        raise NotFoundException("Configurations", None)

    total_count = await configuration_service.get_configurations_count()

    return {"configurations": configurations, "total": total_count, "page": page, "limit": limit}

@router.get("/{configuration_id}", status_code=status.HTTP_200_OK, response_model=ConfigurationResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_configuration_by_id(
    configuration_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    configuration_service: IConfigurationService = Depends(get_configuration_service)
):
    """
    Restituisce una singola configuration basata sull'ID specificato.

    - **configuration_id**: Identificativo della configuration da ricercare.
    """
    configuration = await configuration_service.get_configuration(configuration_id)
    return configuration

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Configuration creata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_configuration(
    configuration_data: ConfigurationSchema,
    user: dict = Depends(get_current_user),
    configuration_service: IConfigurationService = Depends(get_configuration_service)
):
    """
    Crea una nuova configuration con i dati forniti.
    """
    return await configuration_service.create_configuration(configuration_data)

@router.put("/{configuration_id}", status_code=status.HTTP_200_OK, response_description="Configuration aggiornata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_configuration(
    configuration_data: ConfigurationSchema,
    configuration_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    configuration_service: IConfigurationService = Depends(get_configuration_service)
):
    """
    Aggiorna i dati di una configuration esistente basata sull'ID specificato.

    - **configuration_id**: Identificativo della configuration da aggiornare.
    """
    return await configuration_service.update_configuration(configuration_id, configuration_data)

@router.delete("/{configuration_id}", status_code=status.HTTP_200_OK, response_description="Configuration eliminata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_configuration(
    configuration_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    configuration_service: IConfigurationService = Depends(get_configuration_service)
):
    """
    Elimina una configuration basata sull'ID specificato.

    - **configuration_id**: Identificativo della configuration da eliminare.
    """
    await configuration_service.delete_configuration(configuration_id)