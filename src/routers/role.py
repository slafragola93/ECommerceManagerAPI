"""
Role Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
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
from src.services.auth import authorize
from src.services.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/roles",
    tags=["Role"]
)

def get_role_service(db: db_dependency) -> IRoleService:
    """Dependency injection per Role Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    role_repo = configured_container.resolve_with_session(IRoleRepository, db)
    
    # Crea il service con il repository
    role_service = configured_container.resolve(IRoleService)
    # Inietta il repository nel service
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
    try:
        roles = await role_service.get_roles(page=page, limit=limit)
        if not roles:
            raise HTTPException(status_code=404, detail="Nessun ruolo trovato")

        total_count = await role_service.get_roles_count()

        return {"roles": roles, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{role_id}", status_code=status.HTTP_200_OK, response_model=RoleResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_role_by_id(
    user: dict = Depends(get_current_user),
    role_service: IRoleService = Depends(get_role_service),
    role_id: int = Path(gt=0)
):
    """
    Restituisce un singolo ruolo basato sull'ID specificato.

    - **role_id**: Identificativo del ruolo da ricercare.
    """
    try:
        role = await role_service.get_role(role_id)
        return role
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Ruolo non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Ruolo creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_role(
    role_data: RoleSchema,
    role_service: IRoleService = Depends(get_role_service),
    user: dict = Depends(get_current_user)
):
    """
    Crea un nuovo ruolo con i dati forniti.
    """
    try:
        return await role_service.create_role(role_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{role_id}", status_code=status.HTTP_200_OK, response_description="Ruolo aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_role(
    rs: RoleSchema,
    role_service: IRoleService = Depends(get_role_service),
    role_id: int = Path(gt=0),
    user: dict = Depends(get_current_user)
):
    """
    Aggiorna i dati di un ruolo esistente basato sull'ID specificato.

    - **role_id**: Identificativo del ruolo da aggiornare.
    """
    try:
        return await role_service.update_role(role_id, rs)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Ruolo non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{role_id}", status_code=status.HTTP_200_OK, response_description="Ruolo eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_role(
    user: dict = Depends(get_current_user),
    role_service: IRoleService = Depends(get_role_service),
    role_id: int = Path(gt=0)
):
    """
    Elimina un ruolo basato sull'ID specificato.

    - **role_id**: Identificativo del ruolo da eliminare.
    """
    try:
        await role_service.delete_role(role_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Ruolo non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")