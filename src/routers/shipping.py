from fastapi import APIRouter, Path, HTTPException, Depends
from starlette import status
from .dependencies import db_dependency, user_dependency
from .. import ShippingSchema, ShippingResponseSchema
from src.services.wrap import check_authentication
from ..repository.shipping_repository import ShippingRepository
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/shipments',
    tags=['Shipping'],
)


def get_repository(db: db_dependency) -> ShippingRepository:
    return ShippingRepository(db)


@router.get("/{shipping_id}", status_code=status.HTTP_200_OK, response_model=ShippingResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['R'])
async def get_shipping_by_id(user: user_dependency,
                             sr: ShippingRepository = Depends(get_repository),
                             shipping_id: int = Path(gt=0)):

    shipping = sr.get_by_id(_id=shipping_id)

    if shipping is None:
        raise HTTPException(status_code=404, detail="Spedizione non trovata.")

    return shipping


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Spedizione creata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['C'])
async def create_shipping(user: user_dependency,
                          ss: ShippingSchema,
                          sr: ShippingRepository = Depends(get_repository)):
    sr.create(data=ss)


@router.delete("/{shipping_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Spedizione eliminata.")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['D'])
async def delete_shipping(user: user_dependency,
                          sr: ShippingRepository = Depends(get_repository),
                          shipping_id: int = Path(gt=0)):

    shipping = sr.get_by_id(_id=shipping_id)

    if shipping is None:
        raise HTTPException(status_code=404, detail="Spedizione non trovata.")

    sr.delete(shipping=shipping)


@router.put("/{shipping_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Spedizione modificato")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['U'])
async def update_shipment(user: user_dependency,
                          ss: ShippingSchema,
                          sr: ShippingRepository = Depends(get_repository),
                          shipping_id: int = Path(gt=0)):

    shipping = sr.get_by_id(_id=shipping_id)

    if shipping is None:
        raise HTTPException(status_code=404, detail="Spedizione non trovata.")

    sr.update(edited_shipping=shipping, data=ss)
