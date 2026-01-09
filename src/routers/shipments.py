from fastapi import APIRouter, Depends, Query, Path, Body
from typing import List, Optional
import logging
from sqlalchemy.orm import Session

from sqlalchemy import select
from src.core.container_config import get_configured_container
from src.factories.services.carrier_service_factory import CarrierServiceFactory
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.schemas.dhl_tracking_schema import NormalizedTrackingResponseSchema
from src.schemas.shipment_schema import (
    BulkShipmentCreateRequestSchema,
    BulkShipmentCreateResponseSchema,
    BulkShipmentCreateSuccess,
    BulkShipmentCreateError
)
from src.database import get_db
from src.repository.shipping_repository import ShippingRepository
from src.repository.shipment_document_repository import ShipmentDocumentRepository
from src.core.exceptions import (
    NotFoundException,
    BusinessRuleException,
    ValidationException,
    AuthenticationException,
    InfrastructureException
)
from src.services.routers.auth_service import get_current_user
from src.events.core.event import Event, EventType
from src.events.runtime import emit_event
from src.services.routers.order_service import OrderService
from src.repository.order_repository import OrderRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/shippings", tags=["Shipments"])


def _extract_carrier_error_details(exception: Exception, default_category: Optional[str] = None) -> dict:
    """
    Estrae i dettagli di errore del corriere in modo generico dalle eccezioni.
    Supporta sia la nuova convenzione generica che quella legacy BRT per retrocompatibilità.
    
    Args:
        exception: L'eccezione da cui estrarre i dettagli
        default_category: Categoria di errore di default se non presente nei details
        
    Returns:
        Dict con carrier_error_code, carrier_error_description, carrier_name, error_category
    """
    details = {}
    if hasattr(exception, 'details') and isinstance(exception.details, dict):
        details = exception.details
    
    # Extract carrier_error_code (new generic convention)
    # Fallback to error_code, then to legacy brt_error_code
    carrier_error_code = details.get("carrier_error_code") or details.get("error_code")
    if carrier_error_code is None:
        # Legacy BRT support
        brt_error_code = details.get("brt_error_code")
        if brt_error_code is not None:
            carrier_error_code = brt_error_code
    
    # Extract carrier_error_description (new generic convention)
    # Fallback to error_description, then to legacy brt_code_desc
    carrier_error_description = details.get("carrier_error_description") or details.get("error_description")
    if carrier_error_description is None:
        # Legacy BRT support
        brt_code_desc = details.get("brt_code_desc")
        if brt_code_desc:
            carrier_error_description = brt_code_desc
    
    # Extract carrier_name
    carrier_name = details.get("carrier_name")
    
    # Extract error_category (new generic convention)
    # Fallback to legacy brt_error_category
    error_category = details.get("error_category") or details.get("brt_error_category")
    if error_category is None:
        error_category = default_category
    
    return {
        "carrier_error_code": carrier_error_code,
        "carrier_error_description": carrier_error_description,
        "carrier_name": carrier_name,
        "error_category": error_category
    }


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
    
    # 5. Emetti evento per creazione spedizione
    try:
        awb = result.get("awb", "") if isinstance(result, dict) else ""
        event = Event(
            event_type=EventType.SHIPMENT_CREATED.value,
            data={
                "order_id": order_id,
                "carrier_api_id": carrier_api_id,
                "awb": awb,
                "shipment_data": result
            },
            metadata={
                "source": "shipments.create_shipment",
                "id_order": order_id
            }
        )
        emit_event(event)
        logger.info(f"Event SHIPMENT_CREATED emitted for order {order_id}")
    except Exception as e:
        # Non bloccare la risposta in caso di errori nell'emissione dell'evento
        logger.warning(f"Failed to emit SHIPMENT_CREATED event for order {order_id}: {str(e)}", exc_info=True)
    
    # 6. Aggiorna stato ordine a 4 ("Spedizione Confermata")
    try:
        order_service = OrderService(OrderRepository(db))
        await order_service.update_order_status(order_id, 4)
        logger.info(f"Order {order_id} status updated to 4 (Spedizione Confermata) after shipment creation")
    except Exception as e:
        # Non bloccare la risposta in caso di errori nell'aggiornamento dello stato
        logger.warning(f"Failed to update order {order_id} status to 4: {str(e)}", exc_info=True)
    
    return result


@router.post("/bulk-create", response_model=BulkShipmentCreateResponseSchema)
async def bulk_create_shipments(
    request: BulkShipmentCreateRequestSchema = Body(...),
    user: dict = Depends(get_current_user),
    factory: CarrierServiceFactory = Depends(get_carrier_service_factory),
    db: Session = Depends(get_db)
):
    """
    Crea spedizioni in modo massivo per una lista di ordini (unificato per tutti i corrieri)
    
    Il sistema determina automaticamente quale corriere usare per ogni ordine in base a
    Shipping.id_carrier_api associato all'ordine.
    
    Ogni ordine viene processato indipendentemente: gli errori su singoli ordini
    non bloccano il processing degli altri.
    
    Args:
        request: Richiesta con lista di order_ids
        factory: Factory per selezionare il service corretto
        db: Database session
        
    Returns:
        BulkShipmentCreateResponseSchema con:
        - successful: Lista di spedizioni create (order_id, awb)
        - failed: Lista di errori (order_id, error_type, error_message)
        - summary: Riepilogo (total, successful_count, failed_count)
    """
    from src.models.order import Order
    
    successful = []
    failed = []
    total = len(request.order_ids)
    
    logger.info(f"Starting bulk shipment creation for {total} orders")
    
    for order_id in request.order_ids:
        try:
            # 1. Recupera id_shipping da Order
            stmt = select(Order.id_shipping).where(Order.id_order == order_id)
            result = db.execute(stmt)
            id_shipping = result.scalar_one_or_none()
            
            if not id_shipping:
                failed.append(BulkShipmentCreateError(
                    order_id=order_id,
                    error_type="NOT_FOUND",
                    error_message=f"Order {order_id} has no shipping"
                ))
                logger.warning(f"Order {order_id}: No shipping found")
                continue
            
            # 2. Recupera Shipping per ottenere id_carrier_api
            shipping_repo = ShippingRepository(db)
            shipping_info = shipping_repo.get_carrier_info(id_shipping)
            carrier_api_id = shipping_info.id_carrier_api
            
            if not carrier_api_id:
                failed.append(BulkShipmentCreateError(
                    order_id=order_id,
                    error_type="NO_CARRIER_API",
                    error_message=f"Order {order_id} has no carrier_api assigned"
                ))
                logger.warning(f"Order {order_id}: No carrier_api assigned")
                continue
            
            # 3. Usa factory per ottenere il service corretto
            shipment_service = factory.get_shipment_service(carrier_api_id, db)
            
            # 4. Crea spedizione
            logger.info(f"Creating shipment for order {order_id} with carrier_api_id {carrier_api_id}")
            result = await shipment_service.create_shipment(order_id)
            
            # 5. Estrai awb dal risultato
            awb = result.get("awb", "") if isinstance(result, dict) else ""
            
            if not awb:
                failed.append(BulkShipmentCreateError(
                    order_id=order_id,
                    error_type="SHIPMENT_ERROR",
                    error_message=f"Shipment created but no AWB returned for order {order_id}"
                ))
                logger.warning(f"Order {order_id}: Shipment created but no AWB in response")
                continue
            
            successful.append(BulkShipmentCreateSuccess(
                order_id=order_id,
                awb=awb
            ))
            logger.info(f"Order {order_id}: Shipment created successfully with AWB {awb}")
            
            # Emetti evento per creazione spedizione
            try:
                event = Event(
                    event_type=EventType.SHIPMENT_CREATED.value,
                    data={
                        "order_id": order_id,
                        "carrier_api_id": carrier_api_id,
                        "awb": awb,
                        "shipment_data": result
                    },
                    metadata={
                        "source": "shipments.bulk_create_shipments",
                        "id_order": order_id
                    }
                )
                emit_event(event)
                logger.info(f"Event SHIPMENT_CREATED emitted for order {order_id} in bulk operation")
            except Exception as e:
                # Non bloccare il processing in caso di errori nell'emissione dell'evento
                logger.warning(f"Failed to emit SHIPMENT_CREATED event for order {order_id} in bulk operation: {str(e)}", exc_info=True)
            
            # Aggiorna stato ordine a 4 ("Spedizione Confermata")
            try:
                order_service = OrderService(OrderRepository(db))
                await order_service.update_order_status(order_id, 4)
                logger.info(f"Order {order_id} status updated to 4 (Spedito) after shipment creation in bulk operation")
            except Exception as e:
                # Non bloccare il processing in caso di errori nell'aggiornamento dello stato
                logger.warning(f"Failed to update order {order_id} status to 4 in bulk operation: {str(e)}", exc_info=True)
            
        except NotFoundException as e:
            # Extract carrier error details in generic way
            error_details = _extract_carrier_error_details(e, "not_found")
            
            failed.append(BulkShipmentCreateError(
                order_id=order_id,
                error_type="NOT_FOUND",
                error_message=str(e),
                carrier_error_code=error_details.get("carrier_error_code"),
                carrier_error_description=error_details.get("carrier_error_description"),
                carrier_name=error_details.get("carrier_name"),
                error_category="not_found"
            ))
            logger.warning(f"Order {order_id}: NotFoundException - {str(e)}")
            
        except BusinessRuleException as e:
            # Extract carrier error details in generic way
            error_details = _extract_carrier_error_details(e, "business")
            
            failed.append(BulkShipmentCreateError(
                order_id=order_id,
                error_type="BUSINESS_RULE_ERROR",
                error_message=str(e),
                carrier_error_code=error_details.get("carrier_error_code"),
                carrier_error_description=error_details.get("carrier_error_description"),
                carrier_name=error_details.get("carrier_name"),
                error_category=error_details.get("error_category", "business")
            ))
            logger.warning(f"Order {order_id}: BusinessRuleException - {str(e)}")
            
        except ValidationException as e:
            # Extract carrier error details in generic way
            error_details = _extract_carrier_error_details(e, "validation")
            
            failed.append(BulkShipmentCreateError(
                order_id=order_id,
                error_type="VALIDATION_ERROR",
                error_message=str(e),
                carrier_error_code=error_details.get("carrier_error_code"),
                carrier_error_description=error_details.get("carrier_error_description"),
                carrier_name=error_details.get("carrier_name"),
                error_category="validation"
            ))
            logger.warning(f"Order {order_id}: ValidationException - {str(e)}")
            
        except AuthenticationException as e:
            # Extract carrier error details in generic way
            error_details = _extract_carrier_error_details(e, "authentication")
            
            failed.append(BulkShipmentCreateError(
                order_id=order_id,
                error_type="AUTHENTICATION_ERROR",
                error_message=str(e),
                carrier_error_code=error_details.get("carrier_error_code"),
                carrier_error_description=error_details.get("carrier_error_description"),
                carrier_name=error_details.get("carrier_name"),
                error_category="authentication"
            ))
            logger.warning(f"Order {order_id}: AuthenticationException - {str(e)}")
            
        except InfrastructureException as e:
            # Extract carrier error details in generic way
            error_details = _extract_carrier_error_details(e, "infrastructure")
            
            failed.append(BulkShipmentCreateError(
                order_id=order_id,
                error_type="INFRASTRUCTURE_ERROR",
                error_message=str(e),
                carrier_error_code=error_details.get("carrier_error_code"),
                carrier_error_description=error_details.get("carrier_error_description"),
                carrier_name=error_details.get("carrier_name"),
                error_category="infrastructure"
            ))
            logger.warning(f"Order {order_id}: InfrastructureException - {str(e)}")
            
        except Exception as e:
            # Extract carrier error details in generic way (for any other exception)
            error_details = _extract_carrier_error_details(e, None)
            
            failed.append(BulkShipmentCreateError(
                order_id=order_id,
                error_type="UNKNOWN_ERROR",
                error_message=f"Error creating shipment: {str(e)}",
                carrier_error_code=error_details.get("carrier_error_code"),
                carrier_error_description=error_details.get("carrier_error_description"),
                carrier_name=error_details.get("carrier_name"),
                error_category=error_details.get("error_category")
            ))
            logger.error(f"Order {order_id}: Unexpected error - {str(e)}", exc_info=True)
    
    # Calcola summary
    successful_count = len(successful)
    failed_count = len(failed)
    
    summary = {
        "total": total,
        "successful_count": successful_count,
        "failed_count": failed_count
    }
    
    logger.info(f"Bulk shipment creation completed: {successful_count} successful, {failed_count} failed out of {total} total")
    
    return BulkShipmentCreateResponseSchema(
        successful=successful,
        failed=failed,
        summary=summary
    )


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


@router.delete("/{order_id}/cancel", response_model=dict)
async def cancel_shipment(
    order_id: int,
    user: dict = Depends(get_current_user),
    factory: CarrierServiceFactory = Depends(get_carrier_service_factory),
    db: Session = Depends(get_db)
):
    """
    Cancella una spedizione per un ordine (unificato per tutti i corrieri)
    
    Il sistema determina automaticamente quale corriere usare in base a
    Shipping.id_carrier_api associato all'ordine.
    
    Args:
        order_id: ID dell'ordine per cui cancellare la spedizione
        factory: Factory per selezionare il service corretto
        db: Database session
        
    Returns:
        Dict con risultato cancellazione
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
            f"Order {order_id} has no carrier_api assigned. Cannot cancel shipment.",
            details={"order_id": order_id}
        )
    
    # 3. Usa factory per ottenere il service corretto
    shipment_service = factory.get_shipment_service(carrier_api_id, db)
    
    # 4. Cancella spedizione
    logger.info(f"Cancelling shipment for order {order_id} with carrier_api_id {carrier_api_id}")
    result = await shipment_service.cancel_shipment(order_id)
    
    return result
