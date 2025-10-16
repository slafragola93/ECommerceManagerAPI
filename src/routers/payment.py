"""
Payment Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
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
from src.services.auth import authorize
from src.services.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/payments",
    tags=["Payment"]
)

def get_payment_service(db: db_dependency) -> IPaymentService:
    """Dependency injection per Payment Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    payment_repo = configured_container.resolve_with_session(IPaymentRepository, db)
    
    # Crea il service con il repository
    payment_service = configured_container.resolve(IPaymentService)
    # Inietta il repository nel service
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
    try:
        payments = await payment_service.get_payments(page=page, limit=limit)
        if not payments:
            raise HTTPException(status_code=404, detail="Nessun payment trovato")

        total_count = await payment_service.get_payments_count()

        return {"payments": payments, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{payment_id}", status_code=status.HTTP_200_OK, response_model=PaymentResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_payment_by_id(
    user: dict = Depends(get_current_user),
    payment_service: IPaymentService = Depends(get_payment_service),
    payment_id: int = Path(gt=0)
):
    """
    Restituisce un singolo payment basato sull'ID specificato.

    - **payment_id**: Identificativo del payment da ricercare.
    """
    try:
        payment = await payment_service.get_payment(payment_id)
        return payment
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Payment non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Payment creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_payment(
    payment_data: PaymentSchema,
    payment_service: IPaymentService = Depends(get_payment_service),
    user: dict = Depends(get_current_user)
):
    """
    Crea un nuovo payment con i dati forniti.
    """
    try:
        return await payment_service.create_payment(payment_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{payment_id}", status_code=status.HTTP_200_OK, response_description="Payment aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_payment(
    payment_data: PaymentSchema,
    payment_service: IPaymentService = Depends(get_payment_service),
    payment_id: int = Path(gt=0),
    user: dict = Depends(get_current_user)
):
    """
    Aggiorna i dati di un payment esistente basato sull'ID specificato.

    - **payment_id**: Identificativo del payment da aggiornare.
    """
    try:
        return await payment_service.update_payment(payment_id, payment_data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Payment non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{payment_id}", status_code=status.HTTP_200_OK, response_description="Payment eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_payment(
    user: dict = Depends(get_current_user),
    payment_service: IPaymentService = Depends(get_payment_service),
    payment_id: int = Path(gt=0)
):
    """
    Elimina un payment basato sull'ID specificato.

    - **payment_id**: Identificativo del payment da eliminare.
    """
    try:
        await payment_service.delete_payment(payment_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Payment non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
