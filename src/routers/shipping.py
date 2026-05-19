"""
Shipping Router rifattorizzato seguendo i principi SOLID
"""
from typing import Dict, List, Optional, Sequence

from fastapi import APIRouter, Depends, status, Query, Path
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.services.interfaces.shipping_service_interface import IShippingService
from src.repository.interfaces.shipping_repository_interface import IShippingRepository
from src.schemas.shipping_schema import ShippingSchema, ShippingUpdateSchema, ShippingResponseSchema, AllShippingResponseSchema
from src.core.container import container
from src.core.exceptions import (
    NotFoundException
)
from src.core.dependencies import db_dependency
from src.services.routers.auth_service import get_current_user, require_permission
from src.services.core.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.repository.order_repository import OrderRepository
from src.services.routers.order_document_service import OrderDocumentService
from src.services.routers.order_service import OrderService
from src.models.order import Order
from src.models.order_document import OrderDocument
from src.models.shipping import Shipping

router = APIRouter(
    prefix="/api/v1/shippings",
    tags=["Shipping"],
)


def _resolve_id_orders(db: Session, shipping_ids: Sequence[int]) -> Dict[int, Optional[int]]:
    """
    Risolve in batch l'`id_order` (ultimo) per ogni `id_shipping`.

    Convenzione di dominio: ogni `Shipping` appartiene a un `Order`. In caso di
    riuso (raro), restituiamo l'ID più recente (`MAX(id_order)`) così che il
    client possa correlare la PUT con l'ordine corrente in modo deterministico.
    """
    if not shipping_ids:
        return {}
    rows = (
        db.query(Order.id_shipping, func.max(Order.id_order))
        .filter(Order.id_shipping.in_(shipping_ids))
        .group_by(Order.id_shipping)
        .all()
    )
    return {id_shipping: id_order for id_shipping, id_order in rows}


def _to_shipping_response(shipping: Shipping, db: Session) -> ShippingResponseSchema:
    """Serializza un Shipping in `ShippingResponseSchema` includendo `id_order`."""
    id_order_map = _resolve_id_orders(db, [shipping.id_shipping])
    return ShippingResponseSchema.model_validate(shipping).model_copy(
        update={"id_order": id_order_map.get(shipping.id_shipping)}
    )


def _to_shipping_response_list(
    shippings: Sequence[Shipping], db: Session
) -> List[ShippingResponseSchema]:
    """Serializza una lista di Shipping evitando N+1 query per `id_order`."""
    id_order_map = _resolve_id_orders(db, [s.id_shipping for s in shippings])
    return [
        ShippingResponseSchema.model_validate(s).model_copy(
            update={"id_order": id_order_map.get(s.id_shipping)}
        )
        for s in shippings
    ]

def get_shipping_service(db: db_dependency) -> IShippingService:
    """Dependency injection per Shipping Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    shipping_repo = configured_container.resolve_with_session(IShippingRepository, db)
    shipping_service = configured_container.resolve(IShippingService)
    
    if hasattr(shipping_service, '_shipping_repository'):
        shipping_service._shipping_repository = shipping_repo
    
    return shipping_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllShippingResponseSchema)
@check_authentication
async def get_all_shippings(
    user: dict = Depends(get_current_user),
    shipping_service: IShippingService = Depends(get_shipping_service),
    db: db_dependency = None,
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT),
    _: None = Depends(require_permission("shipments", "read")),
):
    """
    Restituisce tutti i shipping con supporto alla paginazione.

    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    shippings = await shipping_service.get_shippings(page=page, limit=limit)
    if not shippings:
        raise NotFoundException("Shippings", None)

    total_count = await shipping_service.get_shippings_count()

    return {
        "shippings": _to_shipping_response_list(shippings, db),
        "total": total_count,
        "page": page,
        "limit": limit,
    }

@router.get("/{shipping_id}", status_code=status.HTTP_200_OK, response_model=ShippingResponseSchema)
@check_authentication
async def get_shipping_by_id(
    shipping_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    shipping_service: IShippingService = Depends(get_shipping_service),
    db: db_dependency = None,
    _: None = Depends(require_permission("shipments", "read")),
):
    """
    Restituisce un singolo shipping basato sull'ID specificato.

    - **shipping_id**: Identificativo del shipping da ricercare.
    """
    shipping = await shipping_service.get_shipping(shipping_id)
    return _to_shipping_response(shipping, db)

@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=ShippingResponseSchema,
    response_description="Spedizione creato correttamente",
)
@check_authentication
async def create_shipping(
    shipping_data: ShippingSchema,
    user: dict = Depends(get_current_user),
    shipping_service: IShippingService = Depends(get_shipping_service),
    db: db_dependency = None,
    _: None = Depends(require_permission("shipments", "create")),
):
    """
    Crea un nuovo shipping con i dati forniti.

    Risponde con l'oggetto creato (incluso `id_shipping`), così che il client non
    debba effettuare una GET di follow-up per recuperare la PK.
    """
    shipping = await shipping_service.create_shipping(shipping_data)

    # Ricalcolo totali ordine/documento collegati alla nuova spedizione

    ods = OrderDocumentService(db)
    order_service = OrderService(OrderRepository(db))
    order = (
        db.query(Order)
        .filter(Order.id_shipping == getattr(shipping, 'id_shipping', None))
        .order_by(Order.id_order.desc())
        .first()
    )
    if order:
        order_service.recalculate_totals_for_order(order.id_order)
    docs = db.query(OrderDocument).filter(OrderDocument.id_shipping == getattr(shipping, 'id_shipping', None)).all()
    for d in docs:
        ods.recalculate_totals_for_order_document(d.id_order_document, d.type_document)

    return _to_shipping_response(shipping, db)

@router.put(
    "/{shipping_id}",
    status_code=status.HTTP_200_OK,
    response_model=ShippingResponseSchema,
    response_description="Spedizione aggiornato correttamente",
)
@check_authentication
async def update_shipping(
    shipping_data: ShippingUpdateSchema,
    shipping_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    shipping_service: IShippingService = Depends(get_shipping_service),
    db: db_dependency = None,
    _: None = Depends(require_permission("shipments", "update")),
):
    """
    Aggiorna i dati di un shipping esistente basato sull'ID specificato.
    Tutti i campi sono facoltativi - solo i campi inviati verranno aggiornati.

    Risponde con l'oggetto aggiornato (incluso `id_shipping`), così che il client
    non debba effettuare una GET di follow-up per riallineare il proprio stato.

    - **shipping_id**: Identificativo del shipping da aggiornare.
    """
    result = await shipping_service.update_shipping(shipping_id, shipping_data)

    shipping = result.get("shipping") if isinstance(result, dict) else result

    # Ricalcolo totali ordine/documento collegati a questa spedizione

    ods = OrderDocumentService(db)
    order_service = OrderService(OrderRepository(db))
    order = (
        db.query(Order)
        .filter(Order.id_shipping == shipping_id)
        .order_by(Order.id_order.desc())
        .first()
    )
    if order:
        order_service.recalculate_totals_for_order(order.id_order)
    docs = db.query(OrderDocument).filter(OrderDocument.id_shipping == shipping_id).all()
    for d in docs:
        ods.recalculate_totals_for_order_document(d.id_order_document, d.type_document)

    return _to_shipping_response(shipping, db)

@router.delete("/{shipping_id}", status_code=status.HTTP_200_OK, response_description="Spedizione eliminata correttamente")
@check_authentication
async def delete_shipping(
    shipping_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    shipping_service: IShippingService = Depends(get_shipping_service),
    db: db_dependency = None,
    _: None = Depends(require_permission("shipments", "delete")),
):
    """
    Elimina un shipping basato sull'ID specificato.

    - **shipping_id**: Identificativo del shipping da eliminare.
    """
    await shipping_service.delete_shipping(shipping_id)
    # Dopo la cancellazione, ricalcola i totali per azzerare la spedizione
    ods = OrderDocumentService(db)
    order_service = OrderService(OrderRepository(db))
    order = (
        db.query(Order)
        .filter(Order.id_shipping == shipping_id)
        .order_by(Order.id_order.desc())
        .first()
    )
    if order:
        order_service.recalculate_totals_for_order(order.id_order)
    docs = db.query(OrderDocument).filter(OrderDocument.id_shipping == shipping_id).all()
    for d in docs:
        ods.recalculate_totals_for_order_document(d.id_order_document, d.type_document)
