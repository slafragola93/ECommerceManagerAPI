from fastapi import APIRouter, Query, HTTPException, Path, Depends
from starlette import status
from .dependencies import db_dependency, user_dependency, LIMIT_DEFAULT, MAX_LIMIT
from .. import OrderDocumentSchema, AllOrderDocumentResponseSchema, OrderDocumentResponseSchema
from src.services.core.wrap import check_authentication
from ..repository.order_document_repository import OrderDocumentRepository
from ..services.routers.auth_service import authorize

router = APIRouter(
    prefix='/api/v1/order_documents',
    tags=['Order Document']
)


def get_repository(db: db_dependency):
    return OrderDocumentRepository(db)



@router.get("/", status_code=status.HTTP_200_OK, response_model=AllOrderDocumentResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_all_order_documents(
        user: user_dependency,
        odr: OrderDocumentRepository = Depends(get_repository),
        page: int = Query(1, gt=0),
        limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):

    return {"order_details": "TEST", "total": 1, "page": page, "limit": limit}
# 
# 
# @router.get("/{order_detail_id}", status_code=status.HTTP_200_OK, response_model=OrderDetailResponseSchema)
# @check_authentication
# @authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
# async def get_order_detail_by_id(user: user_dependency,
#                                  odr: OrderDocumentRepository = Depends(get_repository),
#                                  order_detail_id: int = Path(gt=0)):
#     order_detail = odr.get_by_id(_id=order_detail_id)
# 
#     if order_detail is None:
#         raise HTTPException(status_code=404, detail="Dettaglio ordine non trovato.")
# 
#     return order_detail
# 
# 
# @router.post("/", status_code=status.HTTP_201_CREATED, response_description="Corriere creato correttamente")
# @check_authentication
# @authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
# async def create_order_detail(user: user_dependency,
#                               ods: OrderDocumentchema,
#                               odr: OrderDocumentRepository = Depends(get_repository),
#                               order_r: OrderRepository = Depends(get_order_repository)):
#     odr.create(data=ods)
# 
#     # Aggiornamento prezzo e peso di Order
#     if ods.real_price is True or ods.real_weight is True:
#         order_details = odr.get_by_id_order(id_order=ods.id_order)
#         if ods.real_price is True:
#             order_r.set_price(id_order=ods.id_order, order_details=order_details)
# 
#         if ods.real_weight is True:
#             order_r.set_weight(id_order=ods.id_order, order_details=order_details)
# 
# 
# @router.put("/{order_detail_id}", status_code=status.HTTP_200_OK,
#             response_description="Dettaglio ordine aggiornato correttamente")
# @check_authentication
# @authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
# async def update_order_detail(user: user_dependency,
#                               ods: OrderDocumentchema,
#                               odr: OrderDocumentRepository = Depends(get_repository),
#                               order_detail_id: int = Path(gt=0)):
#     try:
#         order_detail = odr.get_by_id(_id=order_detail_id)
# 
#         if order_detail is None:
#             raise HTTPException(status_code=404, detail="Dettaglio ordine non trovato.")
# 
#         odr.update(edited_order_detail=order_detail,
#                    data=ods)
# 
#     except IntegrityError:
#         raise HTTPException(status_code=400,
#                             detail="Errore di integrità dei dati. Verifica i valori unici e i vincoli.")
# 
# 
# @router.delete("/{order_detail_id}", status_code=status.HTTP_200_OK,
#                response_description="Dettaglio ordine eliminato correttamente")
# @check_authentication
# @authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
# async def delete_order_detail(user: user_dependency,
#                               odr: OrderDocumentRepository = Depends(get_repository),
#                               order_detail_id: int = Path(gt=0)):
#     order_detail = odr.get_by_id(_id=order_detail_id)
# 
#     if order_detail is None:
#         raise HTTPException(status_code=404, detail="Corriere non trovato")
# 
#     odr.delete(order_detail)
