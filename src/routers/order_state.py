from fastapi import APIRouter, Path, HTTPException, Depends, Query
from starlette import status
from src.models.order_state import OrderState
from .dependencies import db_dependency, user_dependency
from .. import OrderStateSchema
from src.services.wrap import check_authentication
from ..repository.order_state_repository import OrderStateRepository
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/order_state',
    tags=['Order State'],
)


def get_repository(db: db_dependency) -> OrderStateRepository:
    return OrderStateRepository(db)


@router.get("/", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'PREVENTIVI', 'FATTURAZIONE'], permissions_required=['R'])
async def get_all_orders_state(user: user_dependency,
                               osr: OrderStateRepository = Depends(get_repository),
                               page: int = Query(1, gt=0),
                               limit: int = Query(10, gt=0)):
    orders_state = osr.get_all(page=page, limit=limit)

    if not orders_state:
        raise HTTPException(status_code=404, detail="Nessuno stato trovato")

    return orders_state


@router.get("/{order_state_id}", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'PREVENTIVI', 'FATTURAZIONE'], permissions_required=['R'])
async def get_order_state_by_id(user: user_dependency,
                                osr: OrderStateRepository = Depends(get_repository),
                                order_state_id: int = Path(gt=0)):
    order_state = osr.get_by_id(_id=order_state_id)

    if order_state is None:
        raise HTTPException(status_code=404, detail="Stato non trovato")

    return order_state


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Stato creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN',], permissions_required=['C'])
async def create_order_state(user: user_dependency,
                             oss: OrderStateSchema,
                             osr: OrderStateRepository = Depends(get_repository)):

    osr.create(data=oss)


@router.put("/{order_state_id}", status_code=status.HTTP_204_NO_CONTENT)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_order_state(user: user_dependency,
                             oss: OrderStateSchema,
                             osr: OrderStateRepository = Depends(get_repository),
                             order_state_id: int = Path(gt=0)):
    order_state = osr.get_by_id(_id=order_state_id)

    if order_state is None:
        raise HTTPException(status_code=404, detail="Stato non trovato")

    osr.update(edited_order_state=order_state, data=oss)
