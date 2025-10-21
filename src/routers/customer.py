"""
Customer Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Path, UploadFile, File, Form
from src.services.interfaces.customer_service_interface import ICustomerService
from src.repository.interfaces.customer_repository_interface import ICustomerRepository
from src.schemas.customer_schema import CustomerSchema, CustomerResponseSchema
from src.core.container import container
from src.core.exceptions import (
    NotFoundException
)
from src.core.dependencies import db_dependency
from src.services.routers.auth_service import authorize
from src.services.core.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.routers.auth_service import get_current_user
from src.schemas.customer_schema import AllCustomerResponseSchema

router = APIRouter(
    prefix="/api/v1/customers",
    tags=["Customer"],
)

def get_customer_service(db: db_dependency) -> ICustomerService:
    """Dependency injection per Customer Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    customer_repo = configured_container.resolve_with_session(ICustomerRepository, db)
    customer_service = configured_container.resolve(ICustomerService)
    
    if hasattr(customer_service, '_customer_repository'):
        customer_service._customer_repository = customer_repo
    
    return customer_service

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Cliente creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def create_customer(
    customer: CustomerSchema,
    user: dict = Depends(get_current_user),
    customer_service: ICustomerService = Depends(get_customer_service)
):
    """
    Crea un nuovo cliente con i dati forniti.
    """
    return await customer_service.create_customer(customer)

@router.put("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Customer modificato")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_customer(
    cs: CustomerSchema,
    customer_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    customer_service: ICustomerService = Depends(get_customer_service)
):
    """
    Aggiorna i dati di un cliente esistente basato sull'ID specificato.

    - **customer_id**: Identificativo del cliente da aggiornare.
    """
    await customer_service.update_customer(customer_id, cs)

@router.get("/{customer_id}", status_code=status.HTTP_200_OK, response_model=CustomerResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_customer_by_id(
    customer_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    customer_service: ICustomerService = Depends(get_customer_service)
):
    """
    Restituisce un singolo cliente basato sull'ID specificato.

    - **customer_id**: Identificativo del cliente da ricercare.
    """
    customer = await customer_service.get_customer(customer_id)
    return customer

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllCustomerResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_all_customers(
    user: dict = Depends(get_current_user),
    customer_service: ICustomerService = Depends(get_customer_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT),
    lang_ids: Optional[List[int]] = Query(None),
    param: Optional[str] = Query(None),
    with_address: Optional[bool] = Query(False)
):
    """
    Restituisce tutti i clienti con supporto alla paginazione. Se specificato, filtra i clienti per lingua.

    - **id_lang**: Identificativo opzionale della lingua per filtrare i clienti.
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    # Costruisci i filtri
    filters = {}
    if lang_ids:
        filters['lang_ids'] = lang_ids
    if param:
        filters['param'] = param
    if with_address:
        filters['with_address'] = with_address
        
    customers = await customer_service.get_customers(page=page, limit=limit, **filters)
    if not customers:
        raise NotFoundException("Customers", None)

    total_count = await customer_service.get_customers_count(**filters)

    return {"customers": customers, "total": total_count, "page": page, "limit": limit}

@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Cliente eliminato.")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
async def delete_customer(
    customer_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    customer_service: ICustomerService = Depends(get_customer_service)
):
    """
    Elimina un cliente basato sull'ID specificato.

    - **customer_id**: Identificativo del cliente da eliminare.
    """
    await customer_service.delete_customer(customer_id)