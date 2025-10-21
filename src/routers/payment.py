"""
Payment Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Path, UploadFile, File, Form
from src.services.interfaces.payment_service_interface import IPaymentService
from src.repository.interfaces.payment_repository_interface import IPaymentRepository
from src.schemas.payment_schema import PaymentSchema, PaymentResponseSchema, AllPaymentsResponseSchema
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
    prefix="/api/v1/payments",
    tags=["Payment"],
)

def get_payment_service(db: db_dependency) -> IPaymentService:
    """Dependency injection per Payment Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    payment_repo = configured_container.resolve_with_session(IPaymentRepository, db)
    payment_service = configured_container.resolve(IPaymentService)
    
    if hasattr(payment_service, '_payment_repository'):
        payment_service._payment_repository = payment_repo
    
    return payment_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllPaymentsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_payments(
    user: dict = Depends(get_current_user),
    payment_service: IPaymentService = Depends(get_payment_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i payment con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    payments = await payment_service.get_payments(page=page, limit=limit)
    if not payments:
        raise NotFoundException("Payments", None)

    total_count = await payment_service.get_payments_count()

    return {"payments": payments, "total": total_count, "page": page, "limit": limit}

@router.get("/{payment_id}", status_code=status.HTTP_200_OK, response_model=PaymentResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_payment_by_id(
    payment_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    payment_service: IPaymentService = Depends(get_payment_service)
):
    """
    Restituisce un singolo payment basato sull'ID specificato.

    - **payment_id**: Identificativo del payment da ricercare.
    """
    payment = await payment_service.get_payment(payment_id)
    return payment

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Payment creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_payment(
    payment_data: PaymentSchema,
    user: dict = Depends(get_current_user),
    payment_service: IPaymentService = Depends(get_payment_service)
):
    """
    Crea un nuovo payment con i dati forniti.
    """
    return await payment_service.create_payment(payment_data)

@router.put("/{payment_id}", status_code=status.HTTP_200_OK, response_description="Payment aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_payment(
    payment_data: PaymentSchema,
    payment_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    payment_service: IPaymentService = Depends(get_payment_service)
):
    """
    Aggiorna i dati di un payment esistente basato sull'ID specificato.

    - **payment_id**: Identificativo del payment da aggiornare.
    """
    return await payment_service.update_payment(payment_id, payment_data)

@router.delete("/{payment_id}", status_code=status.HTTP_200_OK, response_description="Payment eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_payment(
    payment_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    payment_service: IPaymentService = Depends(get_payment_service)
):
    """
    Elimina un payment basato sull'ID specificato.

    - **payment_id**: Identificativo del payment da eliminare.
    """
    await payment_service.delete_payment(payment_id)