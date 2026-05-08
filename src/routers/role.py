"""
Role Router - gestione ruoli e permessi per ruolo
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Path
from src.services.interfaces.role_service_interface import IRoleService
from src.services.interfaces.permission_service_interface import IPermissionService
from src.repository.interfaces.role_repository_interface import IRoleRepository
from src.repository.interfaces.permission_repository_interface import IPermissionRepository
from src.repository.interfaces.user_repository_interface import IUserRepository
from src.schemas.role_schema import RoleSchema, RoleResponseSchema, AllRolesResponseSchema
from src.schemas.permission_schema import (
    RolePermissionsResponseSchema,
    SaveRolePermissionsSchema
)
from src.core.container import container
from src.core.exceptions import (
    BaseApplicationException,
    ValidationException,
    NotFoundException,
    BusinessRuleException
)
from src.core.dependencies import db_dependency
from src.services.routers.auth_service import get_current_user, require_permission
from src.services.core.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT

router = APIRouter(
    prefix="/api/v1/roles",
    tags=["Role"],
)


def get_role_service(db: db_dependency) -> IRoleService:
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    role_repo = configured_container.resolve_with_session(IRoleRepository, db)
    role_service = configured_container.resolve(IRoleService)
    if hasattr(role_service, '_role_repository'):
        role_service._role_repository = role_repo
    return role_service


def get_permission_service(db: db_dependency) -> IPermissionService:
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()

    perm_repo = configured_container.resolve_with_session(IPermissionRepository, db)
    user_repo = configured_container.resolve_with_session(IUserRepository, db)
    role_repo = configured_container.resolve_with_session(IRoleRepository, db)
    perm_service = configured_container.resolve(IPermissionService)

    if hasattr(perm_service, '_permission_repo'):
        perm_service._permission_repo = perm_repo
    if hasattr(perm_service, '_user_repo'):
        perm_service._user_repo = user_repo
    if hasattr(perm_service, '_role_repo'):
        perm_service._role_repo = role_repo
    if hasattr(perm_service, '_db'):
        perm_service._db = db

    return perm_service


# ── CRUD Ruoli ─────────────────────────────────────────────────────────────

@router.get("/", status_code=status.HTTP_200_OK,
            response_model=AllRolesResponseSchema)
@check_authentication
async def get_all_roles(
    user: dict = Depends(get_current_user),
    role_service: IRoleService = Depends(get_role_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT),
    _: None = Depends(require_permission("users", "read")),
):
    """Restituisce tutti i ruoli con paginazione."""
    roles = await role_service.get_roles(page=page, limit=limit)
    if not roles:
        raise NotFoundException("Roles", None)
    total_count = await role_service.get_roles_count()
    return {"roles": roles, "total": total_count, "page": page, "limit": limit}


@router.get("/{role_id}", status_code=status.HTTP_200_OK,
            response_model=RoleResponseSchema)
@check_authentication
async def get_role_by_id(
    role_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    role_service: IRoleService = Depends(get_role_service),
    _: None = Depends(require_permission("users", "read")),
):
    """Restituisce un singolo ruolo per ID."""
    return await role_service.get_role(role_id)


@router.post("/", status_code=status.HTTP_201_CREATED)
@check_authentication
async def create_role(
    role_data: RoleSchema,
    user: dict = Depends(get_current_user),
    role_service: IRoleService = Depends(get_role_service),
    _: None = Depends(require_permission("users", "create")),
):
    """Crea un nuovo ruolo."""
    return await role_service.create_role(role_data)


@router.put("/{role_id}", status_code=status.HTTP_200_OK)
@check_authentication
async def update_role(
    role_data: RoleSchema,
    role_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    role_service: IRoleService = Depends(get_role_service),
    _: None = Depends(require_permission("users", "update")),
):
    """Aggiorna un ruolo esistente."""
    return await role_service.update_role(role_id, role_data)


@router.delete("/{role_id}", status_code=status.HTTP_200_OK)
@check_authentication
async def delete_role(
    role_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    role_service: IRoleService = Depends(get_role_service),
    _: None = Depends(require_permission("users", "delete")),
):
    """
    Elimina un ruolo.
    Bloccato se is_system=True — i ruoli di sistema non si eliminano.
    """
    from src.core.container_config import get_configured_container
    from sqlalchemy.orm import Session
    from src.models.role import Role

    # Verifica is_system prima di eliminare
    role = await role_service.get_role(role_id)
    if hasattr(role, 'is_system') and role.is_system:
        raise BusinessRuleException(
            "Non puoi eliminare un ruolo di sistema",
            details={"role_id": role_id}
        )

    await role_service.delete_role(role_id)
    return {"message": "Ruolo eliminato con successo"}


# ── Permessi del Ruolo ─────────────────────────────────────────────────────

@router.get("/{role_id}/permissions",
            status_code=status.HTTP_200_OK,
            response_model=RolePermissionsResponseSchema)
@check_authentication
async def get_role_permissions(
    role_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    permission_service: IPermissionService = Depends(get_permission_service),
    _: None = Depends(require_permission("users", "read")),
):
    """
    Restituisce la matrice permessi di un ruolo.
    Per ogni modulo mostra i 4 flag can_read/create/update/delete.
    """
    return permission_service.get_role_permissions(role_id)


@router.put("/{role_id}/permissions",
            status_code=status.HTTP_200_OK,
            response_model=RolePermissionsResponseSchema)
@check_authentication
async def save_role_permissions(
    role_id: int = Path(gt=0),
    payload: SaveRolePermissionsSchema = ...,
    user: dict = Depends(get_current_user),
    permission_service: IPermissionService = Depends(get_permission_service),
    _: None = Depends(require_permission("users", "update")),
):
    """
    Salva la matrice permessi di un ruolo.
    Bloccato per ruoli is_system=True.
    """
    return permission_service.save_role_permissions(role_id, payload)