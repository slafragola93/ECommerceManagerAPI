"""
User Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from src.services.interfaces.user_service_interface import IUserService
from src.repository.interfaces.user_repository_interface import IUserRepository
from src.schemas.user_schema import UserSchema, UserResponseSchema
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
    prefix="/api/v1/user",
    tags=["User"],
)

def get_user_service(db: db_dependency) -> IUserService:
    """Dependency injection per User Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    user_repo = configured_container.resolve_with_session(IUserRepository, db)
    
    # Crea il service con il repository
    user_service = configured_container.resolve(IUserService)
    # Inietta il repository nel service
    if hasattr(user_service, '_user_repository'):
        user_service._user_repository = user_repo
    
    return user_service

@router.get("/", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['R'])
async def get_all_users(
    user: dict = Depends(get_current_user),
    user_service: IUserService = Depends(get_user_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti gli utenti con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    try:
        users = await user_service.get_users(page=page, limit=limit)
        if not users:
            raise HTTPException(status_code=404, detail="Nessun utente trovato")

        total_count = await user_service.get_users_count()

        return {
            "users": users,
            "total": total_count,
            "page": page,
            "limit": limit
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{user_id}", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['R'])
async def get_user_by_id(
    user: dict = Depends(get_current_user),
    user_service: IUserService = Depends(get_user_service),
    user_id: int = Path(gt=0)
):
    """
    Restituisce un singolo utente basato sull'ID specificato.

    - **user_id**: Identificativo dell'utente da ricercare.
    """
    try:
        user = await user_service.get_user(user_id)
        return user
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['U'])
async def update_user(
    us: UserSchema,
    user_service: IUserService = Depends(get_user_service),
    user_id: int = Path(gt=0),
    user: dict = Depends(get_current_user)
):
    """
    Aggiorna i dati di un utente esistente basato sull'ID specificato.

    - **user_id**: Identificativo dell'utente da aggiornare.
    """
    try:
        await user_service.update_user(user_id, us)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Utente non trovato.")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Utente eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['D'])
async def delete_user(
    user: dict = Depends(get_current_user),
    user_service: IUserService = Depends(get_user_service),
    user_id: int = Path(gt=0)
):
    """
    Elimina un utente basato sull'ID specificato.

    - **user_id**: Identificativo dell'utente da eliminare.
    """
    try:
        await user_service.delete_user(user_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Utente non trovato.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")