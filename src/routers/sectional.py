"""
Sectional Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from src.services.interfaces.sectional_service_interface import ISectionalService
from src.repository.interfaces.sectional_repository_interface import ISectionalRepository
from src.schemas.sectional_schema import SectionalSchema, SectionalResponseSchema, AllSectionalsResponseSchema
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
    prefix="/api/v1/sectionals",
    tags=["Sectional"]
)

def get_sectional_service(db: db_dependency) -> ISectionalService:
    """Dependency injection per Sectional Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    sectional_repo = configured_container.resolve_with_session(ISectionalRepository, db)
    
    # Crea il service con il repository
    sectional_service = configured_container.resolve(ISectionalService)
    # Inietta il repository nel service
    if hasattr(sectional_service, '_sectional_repository'):
        sectional_service._sectional_repository = sectional_repo
    
    return sectional_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllSectionalsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_sectionals(
    user: dict = Depends(get_current_user),
    sectional_service: ISectionalService = Depends(get_sectional_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i sectional con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    try:
        sectionals = await sectional_service.get_sectionals(page=page, limit=limit)
        if not sectionals:
            raise HTTPException(status_code=404, detail="Nessun sectional trovato")

        total_count = await sectional_service.get_sectionals_count()

        return {"sectionals": sectionals, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{sectional_id}", status_code=status.HTTP_200_OK, response_model=SectionalResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_sectional_by_id(
    user: dict = Depends(get_current_user),
    sectional_service: ISectionalService = Depends(get_sectional_service),
    sectional_id: int = Path(gt=0)
):
    """
    Restituisce un singolo sectional basato sull'ID specificato.

    - **sectional_id**: Identificativo del sectional da ricercare.
    """
    try:
        sectional = await sectional_service.get_sectional(sectional_id)
        return sectional
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Sectional non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Sectional creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_sectional(
    sectional_data: SectionalSchema,
    sectional_service: ISectionalService = Depends(get_sectional_service),
    user: dict = Depends(get_current_user)
):
    """
    Crea un nuovo sectional con i dati forniti.
    """
    try:
        return await sectional_service.create_sectional(sectional_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{sectional_id}", status_code=status.HTTP_200_OK, response_description="Sectional aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_sectional(
    sectional_data: SectionalSchema,
    sectional_service: ISectionalService = Depends(get_sectional_service),
    sectional_id: int = Path(gt=0),
    user: dict = Depends(get_current_user)
):
    """
    Aggiorna i dati di un sectional esistente basato sull'ID specificato.

    - **sectional_id**: Identificativo del sectional da aggiornare.
    """
    try:
        return await sectional_service.update_sectional(sectional_id, sectional_data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Sectional non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{sectional_id}", status_code=status.HTTP_200_OK, response_description="Sectional eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_sectional(
    user: dict = Depends(get_current_user),
    sectional_service: ISectionalService = Depends(get_sectional_service),
    sectional_id: int = Path(gt=0)
):
    """
    Elimina un sectional basato sull'ID specificato.

    - **sectional_id**: Identificativo del sectional da eliminare.
    """
    try:
        await sectional_service.delete_sectional(sectional_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Sectional non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
