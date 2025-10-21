"""
User Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Path, UploadFile, File, Form
from src.services.interfaces.user_service_interface import IUserService
from src.repository.interfaces.user_repository_interface import IUserRepository
from src.schemas.user_schema import UserSchema, UserResponseSchema, AllUsersResponseSchema
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
    prefix="/api/v1/users",
    tags=["User"],
)

def get_user_service(db: db_dependency) -> IUserService:
    """Dependency injection per User Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    user_repo = configured_container.resolve_with_session(IUserRepository, db)
    user_service = configured_container.resolve(IUserService)
    
    if hasattr(user_service, '_user_repository'):
        user_service._user_repository = user_repo
    
    return user_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllUsersResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_users(
    user: dict = Depends(get_current_user),
    user_service: IUserService = Depends(get_user_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti gli user con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    users = await user_service.get_users(page=page, limit=limit)
    if not users:
        raise NotFoundException("Users", None)

    total_count = await user_service.get_users_count()

    return {"users": users, "total": total_count, "page": page, "limit": limit}

@router.get("/{user_id}", status_code=status.HTTP_200_OK, response_model=UserResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_user_by_id(
    user_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    user_service: IUserService = Depends(get_user_service)
):
    """
    Restituisce un singolo user basato sull'ID specificato.

    - **user_id**: Identificativo dell'user da ricercare.
    """
    user = await user_service.get_user(user_id)
    return user

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="User creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_user(
    user_data: UserSchema,
    user: dict = Depends(get_current_user),
    user_service: IUserService = Depends(get_user_service)
):
    """
    Crea un nuovo user con i dati forniti.
    """
    return await user_service.create_user(user_data)

@router.put("/{user_id}", status_code=status.HTTP_200_OK, response_description="User aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_user(
    user_data: UserSchema,
    user_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    user_service: IUserService = Depends(get_user_service)
):
    """
    Aggiorna i dati di un user esistente basato sull'ID specificato.

    - **user_id**: Identificativo dell'user da aggiornare.
    """
    return await user_service.update_user(user_id, user_data)

@router.delete("/{user_id}", status_code=status.HTTP_200_OK, response_description="User eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_user(
    user_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    user_service: IUserService = Depends(get_user_service)
):
    """
    Elimina un user basato sull'ID specificato.

    - **user_id**: Identificativo dell'user da eliminare.
    """
    await user_service.delete_user(user_id)