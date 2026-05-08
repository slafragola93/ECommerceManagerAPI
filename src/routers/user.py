"""
User Router - gestione utenti e permessi per utente
"""
from fastapi import APIRouter, Depends, status, Query, Path
from sqlalchemy.orm import Session
from src.database import get_db
from src.services.interfaces.user_service_interface import IUserService
from src.services.interfaces.permission_service_interface import IPermissionService
from src.repository.interfaces.user_repository_interface import IUserRepository
from src.repository.interfaces.role_repository_interface import IRoleRepository
from src.repository.interfaces.permission_repository_interface import IPermissionRepository
from src.schemas.user_schema import UserSchema, UserResponseSchema, AllUsersResponseSchema, UserRolesUpdateSchema
from src.schemas.permission_schema import (
    UserPermissionsResponseSchema,
    SaveUserPermissionsSchema
)
from src.core.exceptions import (
    ValidationException,
    NotFoundException,
    BusinessRuleException
)
from src.core.dependencies import db_dependency
from src.services.routers.auth_service import get_current_user, require_permission, check_permission
from src.services.core.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT

router = APIRouter(
    prefix="/api/v1/users",
    tags=["User"],
)


def get_user_service(db: db_dependency) -> IUserService:
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    user_repo = configured_container.resolve_with_session(IUserRepository, db)
    role_repo = configured_container.resolve_with_session(IRoleRepository, db)
    user_service = configured_container.resolve(IUserService)
    if hasattr(user_service, '_user_repository'):
        user_service._user_repository = user_repo
    if hasattr(user_service, '_role_repository'):
        user_service._role_repository = role_repo
    return user_service


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


# ── CRUD Utenti ────────────────────────────────────────────────────────────

@router.get("/", status_code=status.HTTP_200_OK,
            response_model=AllUsersResponseSchema)
@check_authentication
async def get_all_users(
    user: dict = Depends(get_current_user),
    user_service: IUserService = Depends(get_user_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT),
    _: None = Depends(require_permission("users", "read")),
):
    """Restituisce tutti gli utenti con paginazione."""
    users = await user_service.get_users(page=page, limit=limit)
    if not users:
        raise NotFoundException("Users", None)
    total_count = await user_service.get_users_count()
    return {"users": users, "total": total_count, "page": page, "limit": limit}


@router.get("/{user_id}", status_code=status.HTTP_200_OK,
            response_model=UserResponseSchema)
@check_authentication
async def get_user_by_id(
    user_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    user_service: IUserService = Depends(get_user_service),
    db: Session = Depends(get_db),
):
    """
    Restituisce un singolo utente per ID.

    - Se user_id == current_user.id: accesso libero (l'utente legge sempre se stesso)
    - Altrimenti: richiede il permesso users.read
    """
    if user_id == user["id"]:
        return await user_service.get_user(user_id)

    check_permission(user, db, "users", "read")

    return await user_service.get_user(user_id)


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=UserResponseSchema)
@check_authentication
async def create_user(
    user_data: UserSchema,
    user: dict = Depends(get_current_user),
    user_service: IUserService = Depends(get_user_service),
    _: None = Depends(require_permission("users", "create")),
):
    """Crea un nuovo utente."""
    return await user_service.create_user(user_data)


@router.put("/{user_id}", status_code=status.HTTP_200_OK, response_model=UserResponseSchema)
@check_authentication
async def update_user(
    user_data: UserSchema,
    user_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    user_service: IUserService = Depends(get_user_service),
    _: None = Depends(require_permission("users", "update")),
):
    """Aggiorna un utente esistente."""
    return await user_service.update_user(user_id, user_data)


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
@check_authentication
async def delete_user(
    user_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    user_service: IUserService = Depends(get_user_service),
    _: None = Depends(require_permission("users", "delete")),
):
    """Elimina un utente."""
    await user_service.delete_user(user_id)
    return {"message": "Utente eliminato con successo"}


@router.put("/{user_id}/roles", status_code=status.HTTP_200_OK,
            response_model=UserResponseSchema)
@check_authentication
async def set_user_roles(
    user_id: int = Path(gt=0),
    body: UserRolesUpdateSchema = ...,
    user: dict = Depends(get_current_user),
    user_service: IUserService = Depends(get_user_service),
    _: None = Depends(require_permission("users", "update")),
):
    """Imposta i ruoli di un utente."""
    return await user_service.set_user_roles(user_id, body.role_ids)


# ── Permessi dell'Utente ───────────────────────────────────────────────────

@router.get("/{user_id}/permissions",
            status_code=status.HTTP_200_OK,
            response_model=UserPermissionsResponseSchema)
@check_authentication
async def get_user_permissions(
    user_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    permission_service: IPermissionService = Depends(get_permission_service),
    _: None = Depends(require_permission("users", "read")),
):
    """
    Restituisce la matrice completa dei permessi di un utente.
    Per ogni modulo mostra i 4 flag e la fonte (role/personal/none).
    """
    return permission_service.get_user_permissions(user_id)


@router.put("/{user_id}/permissions",
            status_code=status.HTTP_200_OK,
            response_model=UserPermissionsResponseSchema)
@check_authentication
async def save_user_permissions(
    user_id: int = Path(gt=0),
    payload: SaveUserPermissionsSchema = ...,
    user: dict = Depends(get_current_user),
    permission_service: IPermissionService = Depends(get_permission_service),
    _: None = Depends(require_permission("users", "update")),
):
    """
    Salva la matrice permessi di un utente.
    Richiede la password dell'admin per conferma.
    """
    admin_id = user["id"]
    return permission_service.save_user_permissions(user_id, payload, admin_id)