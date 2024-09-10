from fastapi import APIRouter, Path, HTTPException, Query, Depends
from starlette import status
from .dependencies import db_dependency, user_dependency, MAX_LIMIT, LIMIT_DEFAULT
from .. import AllPaymentsResponseSchema, PaymentSchema, PaymentResponseSchema
from src.services.wrap import check_authentication
from ..repository.payment_repository import PaymentRepository
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/payment',
    tags=['Payment'],
)


def get_repository(db: db_dependency) -> PaymentRepository:
    return PaymentRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllPaymentsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_all_payments(user: user_dependency,
                           pr: PaymentRepository = Depends(get_repository),
                           page: int = Query(1, gt=0),
                           limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)):
    """
    Restituisce l'elenco di tutti i sezionali disponibili.
    """

    payments = pr.get_all(page=page, limit=limit)

    if not payments:
        raise HTTPException(status_code=404, detail="Nessun sezionale trovato")

    total_count = pr.get_count()

    return {"payments": payments, "total": total_count, "page": page, "limit": limit}


@router.get("/all", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_list_all_payments(user: user_dependency,
                                pr: PaymentRepository = Depends(get_repository)):

    payments = pr.list_all()

    if not payments:
        raise HTTPException(status_code=404, detail="Nessun sezionale trovato")

    return payments


@router.get("/{payment_id}", status_code=status.HTTP_200_OK, response_model=PaymentResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_payment_by_id(user: user_dependency,
                            pr: PaymentRepository = Depends(get_repository),
                            payment_id: int = Path(gt=0)):
    """
    Restituisce un sezionale specificato dall'ID.

    - **payment_id**: ID del sezionale da ricercare.
    """
    payment = pr.get_by_id(_id=payment_id)

    if payment is None:
        raise HTTPException(status_code=404, detail="Metodo pagamento non trovato")

    return payment


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Sezionale creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def create_payment(user: user_dependency,
                         ps: PaymentSchema,
                         pr: PaymentRepository = Depends(get_repository)):
    """
    Crea una nuovo sezionale

    - **ss**: Schema del sezionale contenente i dati per la creazione.
    """

    pr.create(data=ps)


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_description="Sezionale eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
async def delete_payment(user: user_dependency,
                         pr: PaymentRepository = Depends(get_repository),
                         payment_id: int = Path(gt=0)):
    """
    Elimina il marchio specificato dall'ID.

    - **payment_id**: ID del sezionale da eliminare.
    """

    payment = pr.get_by_id(_id=payment_id)

    if payment is None:
        raise HTTPException(status_code=404, detail="Sezionale non trovato.")

    pr.delete(payment=payment)


@router.put("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_payment(user: user_dependency,
                         ps: PaymentSchema,
                         pr: PaymentRepository = Depends(get_repository),
                         payment_id: int = Path(gt=0)):
    """
    Aggiorna i dettagli del sezionale specificato dall'ID con i nuovi dati forniti.

    - **payment_id**: ID del sezionale da eliminare.
    """

    payment = pr.get_by_id(_id=payment_id)

    if payment is None:
        raise HTTPException(status_code=404, detail="Sezionale non trovata.")

    pr.update(edited_payment=payment, data=ps)
