"""
OrderState Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Path, UploadFile, File, Form
from src.services.interfaces.order_state_service_interface import IOrderStateService
from src.repository.interfaces.order_state_repository_interface import IOrderStateRepository
from src.schemas.order_state_schema import OrderStateSchema, OrderStateResponseSchema, AllOrdersStateResponseSchema
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
    prefix="/api/v1/order-states",
    tags=["OrderState"],
)

def get_order_state_service(db: db_dependency) -> IOrderStateService:
    """Dependency injection per OrderState Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    order_state_repo = configured_container.resolve_with_session(IOrderStateRepository, db)
    order_state_service = configured_container.resolve(IOrderStateService)
    
    if hasattr(order_state_service, '_order_state_repository'):
        order_state_service._order_state_repository = order_state_repo
    
    return order_state_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllOrdersStateResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_order_states(
    user: dict = Depends(get_current_user),
    order_state_service: IOrderStateService = Depends(get_order_state_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti gli order_state con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    order_states = await order_state_service.get_order_states(page=page, limit=limit)
    if not order_states:
        raise NotFoundException("OrderStates", None)

    total_count = await order_state_service.get_order_states_count()

    return {"states": order_states, "total": total_count, "page": page, "limit": limit}

@router.get("/{order_state_id}", status_code=status.HTTP_200_OK, response_model=OrderStateResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_order_state_by_id(
    order_state_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    order_state_service: IOrderStateService = Depends(get_order_state_service)
):
    """
    Restituisce un singolo order_state basato sull'ID specificato.

    - **order_state_id**: Identificativo dell'order_state da ricercare.
    """
    order_state = await order_state_service.get_order_state(order_state_id)
    return order_state

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="OrderState creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_order_state(
    order_state_data: OrderStateSchema,
    user: dict = Depends(get_current_user),
    order_state_service: IOrderStateService = Depends(get_order_state_service)
):
    """
    Crea un nuovo order_state con i dati forniti.
    """
    return await order_state_service.create_order_state(order_state_data)

@router.put("/{order_state_id}", status_code=status.HTTP_200_OK, response_description="OrderState aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_order_state(
    order_state_data: OrderStateSchema,
    order_state_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    order_state_service: IOrderStateService = Depends(get_order_state_service)
):
    """
    Aggiorna i dati di un order_state esistente basato sull'ID specificato.

    - **order_state_id**: Identificativo dell'order_state da aggiornare.
    """
    return await order_state_service.update_order_state(order_state_id, order_state_data)

@router.delete("/{order_state_id}", status_code=status.HTTP_200_OK, response_description="OrderState eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_order_state(
    order_state_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    order_state_service: IOrderStateService = Depends(get_order_state_service)
):
    """
    Elimina un order_state basato sull'ID specificato.

    - **order_state_id**: Identificativo dell'order_state da eliminare.
    """
    await order_state_service.delete_order_state(order_state_id)