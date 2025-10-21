"""
Role Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Path, UploadFile, File, Form
from src.services.interfaces.role_service_interface import IRoleService
from src.repository.interfaces.role_repository_interface import IRoleRepository
from src.schemas.role_schema import RoleSchema, RoleResponseSchema, AllRolesResponseSchema
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
    prefix="/api/v1/roles",
    tags=["Role"],
)

def get_role_service(db: db_dependency) -> IRoleService:
    """Dependency injection per Role Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    role_repo = configured_container.resolve_with_session(IRoleRepository, db)
    role_service = configured_container.resolve(IRoleService)
    
    if hasattr(role_service, '_role_repository'):
        role_service._role_repository = role_repo
    
    return role_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllRolesResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_roles(
    user: dict = Depends(get_current_user),
    role_service: IRoleService = Depends(get_role_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i ruoli con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    roles = await role_service.get_roles(page=page, limit=limit)
    if not roles:
        raise NotFoundException("Roles", None)

    total_count = await role_service.get_roles_count()

    return {"roles": roles, "total": total_count, "page": page, "limit": limit}

@router.get("/{role_id}", status_code=status.HTTP_200_OK, response_model=RoleResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_role_by_id(
    role_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    role_service: IRoleService = Depends(get_role_service)
):
    """
    Restituisce un singolo ruolo basato sull'ID specificato.

    - **role_id**: Identificativo del ruolo da ricercare.
    """
    role = await role_service.get_role(role_id)
    return role

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Ruolo creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_role(
    role_data: RoleSchema,
    user: dict = Depends(get_current_user),
    role_service: IRoleService = Depends(get_role_service)
):
    """
    Crea un nuovo ruolo con i dati forniti.
    """
    return await role_service.create_role(role_data)

@router.put("/{role_id}", status_code=status.HTTP_200_OK, response_description="Ruolo aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_role(
    role_data: RoleSchema,
    role_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    role_service: IRoleService = Depends(get_role_service)
):
    """
    Aggiorna i dati di un ruolo esistente basato sull'ID specificato.

    - **role_id**: Identificativo del ruolo da aggiornare.
    """
    return await role_service.update_role(role_id, role_data)

@router.delete("/{role_id}", status_code=status.HTTP_200_OK, response_description="Ruolo eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_role(
    role_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    role_service: IRoleService = Depends(get_role_service)
):
    """
    Elimina un ruolo basato sull'ID specificato.

    - **role_id**: Identificativo del ruolo da eliminare.
    """
    await role_service.delete_role(role_id)