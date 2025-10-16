"""
Carrier Assignment Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from src.services.interfaces.carrier_assignment_service_interface import ICarrierAssignmentService
from src.repository.interfaces.carrier_assignment_repository_interface import ICarrierAssignmentRepository
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.schemas.carrier_assignment_schema import (
    CarrierAssignmentSchema, 
    CarrierAssignmentUpdateSchema, 
    CarrierAssignmentResponseSchema, 
    AllCarrierAssignmentsResponseSchema
)
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
    prefix="/api/v1/carrier_assignments",
    tags=["CarrierAssignment"],
)

def get_carrier_assignment_service(db: db_dependency) -> ICarrierAssignmentService:
    """Dependency injection per Carrier Assignment Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    carrier_assignment_repo = configured_container.resolve_with_session(ICarrierAssignmentRepository, db)
    api_carrier_repo = configured_container.resolve_with_session(IApiCarrierRepository, db)
    carrier_assignment_service = configured_container.resolve(ICarrierAssignmentService)
    
    if hasattr(carrier_assignment_service, '_carrier_assignment_repository'):
        carrier_assignment_service._carrier_assignment_repository = carrier_assignment_repo
    if hasattr(carrier_assignment_service, '_api_carrier_repository'):
        carrier_assignment_service._api_carrier_repository = api_carrier_repo
    
    return carrier_assignment_service


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllCarrierAssignmentsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['R'])
async def get_all_carrier_assignments(
    user: dict = Depends(get_current_user),
    carrier_assignment_service: ICarrierAssignmentService = Depends(get_carrier_assignment_service),
    carrier_assignments_ids: Optional[str] = None,
    carrier_apis_ids: Optional[str] = None,
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Recupera una lista di assegnazioni di corrieri filtrata in base a vari criteri.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `carrier_assignments_ids`: ID delle assegnazioni, separati da virgole.
    - `carrier_apis_ids`: ID dei carrier API, separati da virgole.
    - `page`: Pagina corrente per la paginazione.
    - `limit`: Numero di record per pagina.
    """
    try:
        filters = {
            'carrier_assignments_ids': carrier_assignments_ids,
            'carrier_apis_ids': carrier_apis_ids
        }
        
        assignments = await carrier_assignment_service.get_carrier_assignments(
            page=page, limit=limit, **filters
        )
        
        if not assignments:
            raise HTTPException(status_code=404, detail="Nessuna assegnazione di corriere trovata")

        total_count = await carrier_assignment_service.get_carrier_assignments_count(**filters)

        return {"carrier_assignments": assignments, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{assignment_id}", status_code=status.HTTP_200_OK, response_model=CarrierAssignmentResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['R'])
async def get_carrier_assignment_by_id(
    user: dict = Depends(get_current_user),
    carrier_assignment_service: ICarrierAssignmentService = Depends(get_carrier_assignment_service),
    assignment_id: int = Path(gt=0)
):
    """
    Recupera un'assegnazione di corriere per ID.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `assignment_id`: ID dell'assegnazione da recuperare.
    """
    try:
        assignment = await carrier_assignment_service.get_carrier_assignment(assignment_id)
        return assignment
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Assegnazione di corriere non trovata")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=CarrierAssignmentResponseSchema, response_description="Assegnazione di corriere creata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_carrier_assignment(
    assignment_data: CarrierAssignmentSchema,
    user: dict = Depends(get_current_user),
    carrier_assignment_service: ICarrierAssignmentService = Depends(get_carrier_assignment_service)
):
    """
    Crea una nuova assegnazione di corriere con i dati forniti.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `assignment_data`: Schema dell'assegnazione da creare.
    """
    try:
        assignment = await carrier_assignment_service.create_carrier_assignment(assignment_data)
        return assignment
    except (ValidationException, BusinessRuleException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/{assignment_id}", status_code=status.HTTP_200_OK, response_model=CarrierAssignmentResponseSchema, response_description="Assegnazione di corriere aggiornata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_carrier_assignment(
    assignment_data: CarrierAssignmentUpdateSchema,
    user: dict = Depends(get_current_user),
    carrier_assignment_service: ICarrierAssignmentService = Depends(get_carrier_assignment_service),
    assignment_id: int = Path(gt=0)
):
    """
    Aggiorna un'assegnazione di corriere esistente con aggiornamenti parziali.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `assignment_data`: Schema dell'assegnazione con i campi da aggiornare (tutti opzionali).
    - `assignment_id`: ID dell'assegnazione da aggiornare.
    """
    try:
        assignment = await carrier_assignment_service.update_carrier_assignment(assignment_id, assignment_data)
        return assignment
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Assegnazione di corriere non trovata")
    except (ValidationException, BusinessRuleException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/{assignment_id}", status_code=status.HTTP_200_OK, response_description="Assegnazione di corriere eliminata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_carrier_assignment(
    user: dict = Depends(get_current_user),
    carrier_assignment_service: ICarrierAssignmentService = Depends(get_carrier_assignment_service),
    assignment_id: int = Path(gt=0)
):
    """
    Elimina un'assegnazione di corriere dal sistema per l'ID specificato.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `assignment_id`: ID dell'assegnazione da eliminare.
    """
    try:
        success = await carrier_assignment_service.delete_carrier_assignment(assignment_id)
        if not success:
            raise HTTPException(status_code=500, detail="Errore durante l'eliminazione dell'assegnazione carrier.")
        return {"message": "Assegnazione di corriere eliminata correttamente"}
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Assegnazione di corriere non trovata")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Endpoint aggiuntivi per la gestione delle assegnazioni

@router.post("/find-match", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def find_matching_assignment(
    user: dict = Depends(get_current_user),
    carrier_assignment_service: ICarrierAssignmentService = Depends(get_carrier_assignment_service),
    postal_code: Optional[str] = Query(None),
    country_id: Optional[int] = Query(None),
    origin_carrier_id: Optional[int] = Query(None),
    weight: Optional[float] = Query(None)
):
    """
    Trova l'assegnazione di corriere che corrisponde ai criteri specificati.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `postal_code`: Codice postale per la ricerca.
    - `country_id`: ID del paese per la ricerca.
    - `origin_carrier_id`: ID del corriere di origine per la ricerca.
    - `weight`: Peso del pacco per la ricerca.
    """
    try:
        assignment = await carrier_assignment_service.find_matching_assignment(
            postal_code=postal_code,
            country_id=country_id,
            origin_carrier_id=origin_carrier_id,
            weight=weight
        )
        
        if assignment is None:
            return {
                "message": "Nessuna assegnazione trovata per i criteri specificati",
                "assignment": None
            }
        
        return {
            "message": "Assegnazione trovata",
            "assignment": assignment
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
