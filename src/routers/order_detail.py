from typing import Optional
from fastapi import APIRouter, Query, HTTPException, Path, Depends
from sqlalchemy.exc import IntegrityError
from starlette import status
from .dependencies import db_dependency, user_dependency, LIMIT_DEFAULT, MAX_LIMIT
from .. import OrderDetailSchema, AllOrderDetailsResponseSchema, OrderDetailResponseSchema
from src.services.wrap import check_authentication
from ..repository.order_detail_repository import OrderDetailRepository
from ..repository.order_repository import OrderRepository
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/order_details',
    tags=['Order Detail']
)


def get_repository(db: db_dependency):
    return OrderDetailRepository(db)


def get_order_repository(db: db_dependency):
    return OrderRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllOrderDetailsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_all_order_details(
        user: user_dependency,
        odr: OrderDetailRepository = Depends(get_repository),
        order_details_ids: Optional[str] = None,
        order_ids: Optional[str] = None,
        invoice_ids: Optional[str] = None,
        document_ids: Optional[str] = None,
        origin_ids: Optional[str] = None,
        product_ids: Optional[str] = None,
        search_value: Optional[str] = None,
        rda: Optional[str] = None,
        page: int = Query(1, gt=0),
        limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    order_details = odr.get_all(order_details_ids=order_details_ids,
                                order_ids=order_ids,
                                invoice_ids=invoice_ids,
                                document_ids=document_ids,
                                origin_ids=origin_ids,
                                product_ids=product_ids,
                                search_value=search_value,
                                rda=rda,
                                page=page,
                                limit=limit)

    if not order_details:
        raise HTTPException(status_code=404, detail="Nessun corriere trovato")

    total_count = odr.get_count(order_details_ids=order_details_ids,
                                order_ids=order_ids,
                                invoice_ids=invoice_ids,
                                document_ids=document_ids,
                                origin_ids=origin_ids,
                                product_ids=product_ids,
                                search_value=search_value,
                                rda=rda)
    print(order_details)
    return {"order_details": order_details, "total": total_count, "page": page, "limit": limit}


@router.get("/{order_detail_id}", status_code=status.HTTP_200_OK, response_model=OrderDetailResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_order_detail_by_id(user: user_dependency,
                                 odr: OrderDetailRepository = Depends(get_repository),
                                 order_detail_id: int = Path(gt=0)):
    order_detail = odr.get_by_id(_id=order_detail_id)

    if order_detail is None:
        raise HTTPException(status_code=404, detail="Dettaglio ordine non trovato.")

    return order_detail


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Corriere creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def create_order_detail(user: user_dependency,
                              ods: OrderDetailSchema,
                              odr: OrderDetailRepository = Depends(get_repository)):
    odr.create(data=ods)




@router.put("/{order_detail_id}", status_code=status.HTTP_200_OK,
            response_description="Dettaglio ordine aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_order_detail(user: user_dependency,
                              ods: OrderDetailSchema,
                              odr: OrderDetailRepository = Depends(get_repository),
                              order_detail_id: int = Path(gt=0)):
    try:
        order_detail = odr.get_by_id(_id=order_detail_id)

        if order_detail is None:
            raise HTTPException(status_code=404, detail="Dettaglio ordine non trovato.")

        odr.update(edited_order_detail=order_detail,
                   data=ods)

    except IntegrityError:
        raise HTTPException(status_code=400,
                            detail="Errore di integrità dei dati. Verifica i valori unici e i vincoli.")


@router.delete("/{order_detail_id}", status_code=status.HTTP_200_OK,
               response_description="Dettaglio ordine eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
async def delete_order_detail(user: user_dependency,
                              odr: OrderDetailRepository = Depends(get_repository),
                              order_detail_id: int = Path(gt=0)):
    order_detail = odr.get_by_id(_id=order_detail_id)

    if order_detail is None:
        raise HTTPException(status_code=404, detail="Corriere non trovato")

    odr.delete(order_detail)
