from fastapi import APIRouter, Depends
from starlette import status
from .dependencies import db_dependency, user_dependency
from .. import OrderSchema
from src.services.wrap import check_authentication
from ..repository.order_repository import OrderRepository
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/orders',
    tags=['Order'],
)


def get_repository(db: db_dependency) -> OrderRepository:
    return OrderRepository(db)


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Cliente creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def create_order(user: user_dependency,
                       order: OrderSchema,
                       cr: OrderRepository = Depends(get_repository)):
    """
    Crea un nuovo cliente con i dati forniti.
    """

    cr.create(data=order)

    # cr.update_order_status(id_order=id_new_order, id_order_state=1)

