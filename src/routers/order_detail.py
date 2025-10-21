"""
Order Detail Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from src.services.interfaces.order_detail_service_interface import IOrderDetailService
from src.repository.interfaces.order_detail_repository_interface import IOrderDetailRepository
from src.schemas.order_detail_schema import OrderDetailSchema, OrderDetailResponseSchema, AllOrderDetailsResponseSchema
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
    prefix="/api/v1/order_details",
    tags=["OrderDetail"],
)

def get_order_detail_service(db: db_dependency) -> IOrderDetailService:
    """Dependency injection per Order Detail Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    order_detail_repo = configured_container.resolve_with_session(IOrderDetailRepository, db)
    order_detail_service = configured_container.resolve(IOrderDetailService)
    if hasattr(order_detail_service, '_order_detail_repository'):
        order_detail_service._order_detail_repository = order_detail_repo
    
    return order_detail_service


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllOrderDetailsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_all_order_details(
    user: dict = Depends(get_current_user),
    order_detail_service: IOrderDetailService = Depends(get_order_detail_service),
    order_ids: Optional[str] = None,
    order_document_ids: Optional[str] = None,
    product_ids: Optional[str] = None,
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Recupera una lista di dettagli ordine filtrata in base a vari criteri.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `order_ids`: ID degli ordini, separati da virgole.
    - `order_document_ids`: ID dei documenti ordine, separati da virgole.
    - `product_ids`: ID dei prodotti, separati da virgole.
    - `page`: Pagina corrente per la paginazione.
    - `limit`: Numero di record per pagina.
    """
    filters = {
            'order_ids': order_ids,
            'order_document_ids': order_document_ids,
            'product_ids': product_ids
        }
        
    order_details = await order_detail_service.get_order_details(
        page=page, limit=limit, **filters
    )
    
    if not order_details:
        raise HTTPException(status_code=404, detail="Nessun dettaglio ordine trovato")

    total_count = await order_detail_service.get_order_details_count(**filters)

    return {"order_details": order_details, "total": total_count, "page": page, "limit": limit}


@router.get("/{order_detail_id}", status_code=status.HTTP_200_OK, response_model=OrderDetailResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_order_detail_by_id(
    user: dict = Depends(get_current_user),
    order_detail_service: IOrderDetailService = Depends(get_order_detail_service),
    order_detail_id: int = Path(gt=0)
):
    """
    Recupera un dettaglio ordine per ID.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `order_detail_id`: ID del dettaglio ordine da recuperare.
    """
    return await order_detail_service.get_order_detail(order_detail_id)


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=OrderDetailResponseSchema, response_description="Dettaglio ordine creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def create_order_detail(
    order_detail_data: OrderDetailSchema,
    user: dict = Depends(get_current_user),
    order_detail_service: IOrderDetailService = Depends(get_order_detail_service)
):
    """
    Crea un nuovo dettaglio ordine con i dati forniti.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `order_detail_data`: Schema del dettaglio ordine da creare.
    """
    return await order_detail_service.create_order_detail(order_detail_data)




@router.put("/{order_detail_id}", status_code=status.HTTP_200_OK, response_model=OrderDetailResponseSchema, response_description="Dettaglio ordine aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_order_detail(
    order_detail_data: OrderDetailSchema,
    user: dict = Depends(get_current_user),
    order_detail_service: IOrderDetailService = Depends(get_order_detail_service),
    order_detail_id: int = Path(gt=0)
):
    """
    Aggiorna un dettaglio ordine esistente con i nuovi dati forniti.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `order_detail_data`: Schema del dettaglio ordine con i dati aggiornati.
    - `order_detail_id`: ID del dettaglio ordine da aggiornare.
    """
    return await order_detail_service.update_order_detail(order_detail_id, order_detail_data)


@router.delete("/{order_detail_id}", status_code=status.HTTP_200_OK, response_description="Dettaglio ordine eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
async def delete_order_detail(
    user: dict = Depends(get_current_user),
    order_detail_service: IOrderDetailService = Depends(get_order_detail_service),
    order_detail_id: int = Path(gt=0)
):
    """
    Elimina un dettaglio ordine dal sistema.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `order_detail_id`: ID del dettaglio ordine da eliminare.
    """
    success = await order_detail_service.delete_order_detail(order_detail_id)
    if not success:
        raise HTTPException(status_code=500, detail="Errore durante l'eliminazione del dettaglio ordine.")
    return {"message": "Dettaglio ordine eliminato correttamente"}