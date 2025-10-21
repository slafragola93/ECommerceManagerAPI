"""
Carrier Assignment Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Path, UploadFile, File, Form
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
    NotFoundException
)
from src.core.dependencies import db_dependency
from src.services.routers.auth_service import authorize
from src.services.core.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.routers.auth_service import get_current_user

router = APIRouter(
    prefix="/api/v1/carrier-assignments",
    tags=["CarrierAssignment"],
)

def get_carrier_assignment_service(db: db_dependency) -> ICarrierAssignmentService:
    """Dependency injection per CarrierAssignment Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    carrier_assignment_repo = configured_container.resolve_with_session(ICarrierAssignmentRepository, db)
    carrier_assignment_service = configured_container.resolve(ICarrierAssignmentService)
    
    if hasattr(carrier_assignment_service, '_carrier_assignment_repository'):
        carrier_assignment_service._carrier_assignment_repository = carrier_assignment_repo
    
    return carrier_assignment_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllCarrierAssignmentsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_carrier_assignments(
    user: dict = Depends(get_current_user),
    carrier_assignment_service: ICarrierAssignmentService = Depends(get_carrier_assignment_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i carrier_assignment con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    carrier_assignments = await carrier_assignment_service.get_carrier_assignments(page=page, limit=limit)
    if not carrier_assignments:
        raise NotFoundException("CarrierAssignments", None)

    total_count = await carrier_assignment_service.get_carrier_assignments_count()

    return {"carrier_assignments": carrier_assignments, "total": total_count, "page": page, "limit": limit}

@router.get("/{carrier_assignment_id}", status_code=status.HTTP_200_OK, response_model=CarrierAssignmentResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_carrier_assignment_by_id(
    carrier_assignment_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    carrier_assignment_service: ICarrierAssignmentService = Depends(get_carrier_assignment_service)
):
    """
    Restituisce un singolo carrier_assignment basato sull'ID specificato.

    - **carrier_assignment_id**: Identificativo del carrier_assignment da ricercare.
    """
    carrier_assignment = await carrier_assignment_service.get_carrier_assignment(carrier_assignment_id)
    return carrier_assignment

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="CarrierAssignment creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_carrier_assignment(
    carrier_assignment_data: CarrierAssignmentSchema,
    user: dict = Depends(get_current_user),
    carrier_assignment_service: ICarrierAssignmentService = Depends(get_carrier_assignment_service)
):
    """
    Crea un nuovo carrier_assignment con i dati forniti.
    """
    return await carrier_assignment_service.create_carrier_assignment(carrier_assignment_data)

@router.put("/{carrier_assignment_id}", status_code=status.HTTP_200_OK, response_description="CarrierAssignment aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_carrier_assignment(
    carrier_assignment_data: CarrierAssignmentUpdateSchema,
    carrier_assignment_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    carrier_assignment_service: ICarrierAssignmentService = Depends(get_carrier_assignment_service)
):
    """
    Aggiorna i dati di un carrier_assignment esistente basato sull'ID specificato.

    - **carrier_assignment_id**: Identificativo del carrier_assignment da aggiornare.
    """
    return await carrier_assignment_service.update_carrier_assignment(carrier_assignment_id, carrier_assignment_data)

@router.delete("/{carrier_assignment_id}", status_code=status.HTTP_200_OK, response_description="CarrierAssignment eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_carrier_assignment(
    carrier_assignment_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    carrier_assignment_service: ICarrierAssignmentService = Depends(get_carrier_assignment_service)
):
    """
    Elimina un carrier_assignment basato sull'ID specificato.

    - **carrier_assignment_id**: Identificativo del carrier_assignment da eliminare.
    """
    await carrier_assignment_service.delete_carrier_assignment(carrier_assignment_id)