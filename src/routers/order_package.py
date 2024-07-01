from fastapi import APIRouter, Path, HTTPException, Depends
from starlette import status
from .dependencies import db_dependency, user_dependency
from .. import OrderPackageResponseSchema, OrderPackageSchema
from src.services.wrap import check_authentication
from ..repository.order_package_repository import OrderPackageRepository
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/order_packages',
    tags=['OrderPackage'],
)


def get_repository(db: db_dependency) -> OrderPackageRepository:
    return OrderPackageRepository(db)


@router.get("/{order_package_id}", status_code=status.HTTP_200_OK, response_model=OrderPackageResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['R'])
async def get_order_package_by_id(user: user_dependency,
                                  cr: OrderPackageRepository = Depends(get_repository),
                                  order_package_id: int = Path(gt=0)):
    order_package = cr.get_by_id(_id=order_package_id)

    if order_package is None:
        raise HTTPException(status_code=404, detail="Package non trovato")

    return order_package


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Package creata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['C'])
async def create_order_package(user: user_dependency,
                               cs: OrderPackageSchema,
                               cr: OrderPackageRepository = Depends(get_repository)):
    cr.create(data=cs)


@router.delete("/{order_package_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_description="Package eliminata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['D'])
async def delete_order_package(user: user_dependency,
                               cr: OrderPackageRepository = Depends(get_repository),
                               order_package_id: int = Path(gt=0)):

    order_package = cr.get_by_id(_id=order_package_id)

    if order_package is None:
        raise HTTPException(status_code=404, detail="Package non trovato.")

    cr.delete(order_package=order_package)


@router.put("/{order_package_id}", status_code=status.HTTP_204_NO_CONTENT)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_order_package(user: user_dependency,
                               cs: OrderPackageSchema,
                               cr: OrderPackageRepository = Depends(get_repository),
                               order_package_id: int = Path(gt=0)):

    order_package = cr.get_by_id(_id=order_package_id)

    if order_package is None:
        raise HTTPException(status_code=404, detail="Package non trovato.")

    cr.update(edited_order_package=order_package, data=cs)
