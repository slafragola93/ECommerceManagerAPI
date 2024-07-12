from typing import Optional
from fastapi import APIRouter, Path, HTTPException, Query, Depends
from starlette import status
from .dependencies import db_dependency, user_dependency, LIMIT_DEFAULT, MAX_LIMIT
from .. import CustomerSchema, AllCustomerResponseSchema, CustomerResponseSchema
from src.services.wrap import check_authentication
from ..repository.customer_repository import CustomerRepository
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/customers',
    tags=['Customer'],
)


def get_repository(db: db_dependency) -> CustomerRepository:
    return CustomerRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllCustomerResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_all_customers(
        user: user_dependency,
        cr: CustomerRepository = Depends(get_repository),
        param: Optional[str] = None,
        with_address: Optional[bool] = False,
        lang_ids: Optional[str] = None,
        page: int = Query(1, gt=0),
        limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i clienti con supporto alla paginazione. Se specificato, filtra i clienti per lingua.

    - **id_lang**: Identificativo opzionale della lingua per filtrare i clienti.
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """

    customers = cr.get_all(page=page, limit=limit, with_address=with_address, lang_ids=lang_ids, param=param)
    if not customers:
        raise HTTPException(status_code=404, detail="Nessun cliente trovato")

    total_count = cr.get_count(lang_ids=lang_ids, param=param)

    return {"customers": customers, "total": total_count, "page": page, "limit": limit}


@router.get("/{customer_id}", status_code=status.HTTP_200_OK, response_model=CustomerResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_customer_by_id(user: user_dependency,
                             cr: CustomerRepository = Depends(get_repository),
                             customer_id: int = Path(gt=0)):
    """
    Restituisce un singolo cliente basato sull'ID specificato.

    - **customer_id**: Identificativo del cliente da ricercare.
    """

    customer = cr.get_by_id(_id=customer_id)

    if customer is None:
        raise HTTPException(status_code=404, detail="Cliente non trovato.")

    return customer


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Cliente creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def create_customer(user: user_dependency,
                          customer: CustomerSchema,
                          cr: CustomerRepository = Depends(get_repository)):
    """
    Crea un nuovo cliente con i dati forniti.
    """

    cr.create(data=customer)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Cliente eliminato.")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
async def delete_customer(user: user_dependency,
                          cr: CustomerRepository = Depends(get_repository),
                          customer_id: int = Path(gt=0)):
    """
    Elimina un cliente basato sull'ID specificato.

    - **customer_id**: Identificativo del cliente da eliminare.
    """

    customer = cr.get_by_id(_id=customer_id)

    if customer is None:
        raise HTTPException(status_code=404, detail="Cliente non trovato.")

    cr.delete(customer=customer)


@router.put("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Customer modificato")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_customer(user: user_dependency,
                          cs: CustomerSchema,
                          cr: CustomerRepository = Depends(get_repository),
                          customer_id: int = Path(gt=0)):
    """
    Aggiorna i dati di un cliente esistente basato sull'ID specificato.

    - **customer_id**: Identificativo del cliente da aggiornare.
    """

    customer = cr.get_by_id(_id=customer_id)

    if customer is None:
        raise HTTPException(status_code=404, detail="Cliente non trovato.")

    cr.update(edited_customer=customer, data=cs)
