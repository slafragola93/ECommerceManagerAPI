from fastapi import APIRouter, Depends, Query, Path
from typing import List
import logging
from sqlalchemy.orm import Session

from sqlalchemy import select
from src.core.container_config import get_configured_container
from src.factories.services.carrier_service_factory import CarrierServiceFactory
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.schemas.dhl_tracking_schema import NormalizedTrackingResponseSchema
from src.database import get_db
from src.repository.shipping_repository import ShippingRepository
from src.repository.shipment_document_repository import ShipmentDocumentRepository
from src.core.exceptions import NotFoundException, BusinessRuleException
from src.services.routers.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/shippings", tags=["Shipments"])


def get_carrier_repo(db: Session = Depends(get_db)) -> IApiCarrierRepository:
    """Dependency to get carrier API repository"""
    configured_container = get_configured_container()
    return configured_container.resolve_with_session(IApiCarrierRepository, db)


def get_carrier_service_factory(
    carrier_repo: IApiCarrierRepository = Depends(get_carrier_repo)
) -> CarrierServiceFactory:
    """Dependency to get carrier service factory"""
    return CarrierServiceFactory(carrier_repo)


@router.post("/{order_id}/create", response_model=dict)
async def create_shipment(
    order_id: int,
    user: dict = Depends(get_current_user),
    factory: CarrierServiceFactory = Depends(get_carrier_service_factory),
    db: Session = Depends(get_db)
):
    """
    Crea una nuova spedizione per un ordine (unificato per tutti i corrieri)
    
    Il sistema determina automaticamente quale corriere usare in base a
    Shipping.id_carrier_api associato all'ordine.
    
    Args:
        order_id: ID dell'ordine per cui creare la spedizione
        factory: Factory per selezionare il service corretto
        db: Database session
        
    Returns:
        Dict con dettagli spedizione (deve includere 'awb')
    """
    # 1. Recupera id_carrier_api da Shipping tramite Order
    from src.models.order import Order
    
    stmt = select(Order.id_shipping).where(Order.id_order == order_id)
    result = db.execute(stmt)
    id_shipping = result.scalar_one_or_none()
    
    if not id_shipping:
        raise NotFoundException("Order", order_id, {"order_id": order_id, "reason": "Order has no shipping"})
    
    # 2. Recupera Shipping per ottenere id_carrier_api
    shipping_repo = ShippingRepository(db)
    shipping_info = shipping_repo.get_carrier_info(id_shipping)
    carrier_api_id = shipping_info.id_carrier_api
    
    if not carrier_api_id:
        raise BusinessRuleException(
            f"Order {order_id} has no carrier_api assigned. Please assign a carrier first.",
            details={"order_id": order_id}
        )
    
    # 3. Usa factory per ottenere il service corretto
    shipment_service = factory.get_shipment_service(carrier_api_id, db)
    
    # 4. Crea spedizione
    logger.info(f"Creating shipment for order {order_id} with carrier_api_id {carrier_api_id}")
    result = await shipment_service.create_shipment(order_id)
    
    return result


@router.get("/{id_carrier_api}/tracking", response_model=List[NormalizedTrackingResponseSchema])
async def get_tracking(
    id_carrier_api: int = Path(..., description="Carrier API ID for authentication"),
    tracking: str = Query(..., description="Comma-separated list of tracking numbers"),
    user: dict = Depends(get_current_user),
    factory: CarrierServiceFactory = Depends(get_carrier_service_factory),
    db: Session = Depends(get_db)
):
    """
    Recupera informazioni di tracciamento per le spedizioni (unificato per tutti i corrieri)
    
    Il sistema determina automaticamente quale tracking service usare in base a id_carrier_api.
    
    Args:
        id_carrier_api: ID dell'API del carrier per l'autenticazione (path parameter)
        tracking: Numero di tracciamento separato da virgole
        factory: Factory per selezionare il service corretto
        db: Database session
        
    Returns:
        Lista di risposte di tracciamento normalizzate
    """
    
    # Parse tracking numbers
    tracking_list = [tn.strip() for tn in tracking.split(",") if tn.strip()]
    if not tracking_list:
        raise BusinessRuleException("No tracking numbers provided", details={"tracking": tracking})
    
    # Usa factory per ottenere il tracking service corretto
    tracking_service = factory.get_tracking_service(id_carrier_api, db)
    logger.info(f"Getting tracking for {len(tracking_list)} shipments with carrier_api_id {id_carrier_api}")
    
    result = await tracking_service.get_tracking(tracking_list, id_carrier_api)
    # Aggiorna lo stato shipment in base al tracking (se presente)
    try:
        repo = ShippingRepository(db)
        for item in result:
            tn = item.get("tracking_number")
            state_id = item.get("current_internal_state_id")
            if tn and isinstance(state_id, int):
                repo.update_state_by_tracking(tn, state_id)
    except Exception as _:
        # Non bloccare la risposta in caso di problemi di aggiornamento
        logger.warning("Errore in aggiornamento stato spedizione", exc_info=True)
    
    return result


@router.get("/download-label/{awb}")
async def download_shipment_label(
    awb: str,
    user: dict = Depends(get_current_user),
    factory: CarrierServiceFactory = Depends(get_carrier_service_factory),
    db: Session = Depends(get_db)
):
    """
    Scarica il PDF della label per una spedizione (unificato per tutti i corrieri)
    
    Il sistema determina automaticamente quale corriere usare cercando il documento
    nel database o il tracking nella spedizione.
    
    Args:
        awb: Air Waybill number o tracking number
        factory: Factory per selezionare il service corretto
        db: Database session
        
    Returns:
        File PDF della label
    """
    from fastapi.responses import FileResponse
    import os
    
    logger.info(f"Downloading label for AWB: {awb}")
    
    # 1. Cerca documento nel database per ottenere carrier_api_id
    document_repo = ShipmentDocumentRepository(db)
    documents = document_repo.get_by_awb(awb)
    
    carrier_api_id = None
    if documents:
        carrier_api_id = documents[0].carrier_api_id
    
    # 2. Se non trovato, cerca in Shipping.tracking
    if not carrier_api_id:
        from src.models.shipping import Shipping
        
        stmt = select(Shipping.id_carrier_api).where(Shipping.tracking == awb)
        result = db.execute(stmt)
        carrier_api_id = result.scalar_one_or_none()
    
    if not carrier_api_id:
        raise NotFoundException(
            "ShipmentDocument",
            awb,
            {"awb": awb, "reason": "No carrier_api_id associated"}
        )
    
    # 3. Usa factory per ottenere il service corretto
    shipment_service = factory.get_shipment_service(carrier_api_id, db)
    
    # 4. Recupera il percorso del file PDF
    file_path = await shipment_service.get_label_file_path(awb)
    
    if not file_path or not os.path.exists(file_path):
        raise NotFoundException("ShipmentDocument", awb, {"awb": awb, "file_path": file_path})
    
    return FileResponse(
        path=file_path,
        filename=f"label_{awb}.pdf",
        media_type="application/pdf"
    )

