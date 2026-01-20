from fastapi import APIRouter, Depends, Query, Path, Body
from typing import List, Optional
import logging
from sqlalchemy.orm import Session
from src.core.container_config import get_configured_container
from src.factories.services.carrier_service_factory import CarrierServiceFactory
from src.repository.api_carrier_repository import ApiCarrierRepository
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.repository.interfaces.order_repository_interface import IOrderRepository
from src.repository.interfaces.shipment_document_repository_interface import IShipmentDocumentRepository
from src.repository.interfaces.shipping_repository_interface import IShippingRepository
from src.schemas.dhl_tracking_schema import NormalizedTrackingResponseSchema
from src.schemas.shipment_schema import (
    BulkShipmentCreateRequestSchema,
    BulkShipmentCreateResponseSchema,
    BulkShipmentCreateSuccess,
    BulkShipmentCreateError
)
from src.models.order_document import OrderDocument
from sqlalchemy.orm import joinedload, selectinload
from src.schemas.shipping_schema import (
    MultiShippingDocumentCreateRequestSchema,
    MultiShippingDocumentResponseSchema,
    OrderShipmentStatusResponseSchema,
    MultiShippingDocumentListResponseSchema
)
from src.database import get_db
from src.repository.shipping_repository import ShippingRepository
from src.services.interfaces.shipping_service_interface import IShippingService
from src.services.routers.shipping_service import ShippingService
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

def get_repository(db: Session = Depends(get_db)) -> IOrderRepository:
    """Dependency injection per Order Repository."""
    return OrderRepository(db)

def get_shipping_repository(db: Session = Depends(get_db)) -> IShippingRepository:
    """Dependency injection per Shipping Repository."""
    return ShippingRepository(db)

def get_shipment_document_repository(db: Session = Depends(get_db)) -> IShipmentDocumentRepository:
    """Dependency injection per Shipment Document Repository."""
    return ShipmentDocumentRepository(db)

def get_carrier_repository(db: Session = Depends(get_db)) -> IApiCarrierRepository:
    """Dependency injection per Carrier Repository."""
    return ApiCarrierRepository(db)

def get_shipping_service(db: Session = Depends(get_db)) -> IShippingService:
    """Dependency injection per Shipping Service."""
    return ShippingService(db)

def _create_bulk_shipment_error(
    order_id: int,
    exception: Exception,
    error_type: str,
    default_category: Optional[str] = None
) -> BulkShipmentCreateError:
    """
    Crea un BulkShipmentCreateError da un'eccezione.
    Segue il principio Single Responsibility: una funzione per creare l'errore.
    
    Args:
        order_id: ID dell'ordine
        exception: L'eccezione da cui estrarre i dettagli
        error_type: Tipo di errore (es. "NOT_FOUND", "BUSINESS_RULE_ERROR")
        default_category: Categoria di errore di default se non presente nei details
        
    Returns:
        BulkShipmentCreateError configurato
    """
    error_details = _extract_carrier_error_details(exception, default_category)
    
    return BulkShipmentCreateError(
        order_id=order_id,
        error_type=error_type,
        error_message=str(exception),
        carrier_error_code=error_details.get("carrier_error_code"),
        carrier_error_description=error_details.get("carrier_error_description"),
        carrier_name=error_details.get("carrier_name"),
        error_category=error_details.get("error_category", default_category)
    )


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
    or_repo: OrderRepository = Depends(get_repository),
    shipping_repo: ShippingRepository = Depends(get_shipping_repository),
    id_order_document: Optional[int] = Query(None, description="ID OrderDocument type=shipping"),
    user: dict = Depends(get_current_user),
    shipping_service: IShippingService = Depends(get_shipping_service),
    factory: CarrierServiceFactory = Depends(get_carrier_service_factory),
    db: Session = Depends(get_db)
):
    """
    Crea una nuova spedizione per un ordine (unificato per tutti i corrieri)
    
    Il sistema determina automaticamente quale corriere usare in base a
    Shipping.id_carrier_api associato all'ordine.
    
    Se id_order_document è fornito, usa i dati del documento di spedizione multipla.
    
    Args:
        order_id: ID dell'ordine per cui creare la spedizione
        id_order_document: ID opzionale del OrderDocument type=shipping
        factory: Factory per selezionare il service corretto
        db: Database session
        
    Returns:
        Dict con dettagli spedizione (deve includere 'awb')
    """

    if id_order_document:
        # Usa OrderDocument per recuperare i dati
        order_doc = db.query(OrderDocument).options(
            joinedload(OrderDocument.shipping),
            joinedload(OrderDocument.address_delivery),
            selectinload(OrderDocument.order_packages)
        ).filter(
            OrderDocument.id_order_document == id_order_document,
            OrderDocument.type_document == "shipping"
        ).first()
        
        if not order_doc:
            raise NotFoundException("OrderDocument", id_order_document)
        
        id_shipping = order_doc.id_shipping
        if not id_shipping:
            raise NotFoundException("Shipping", None, {"id_order_document": id_order_document, "reason": "OrderDocument has no shipping"})
        
        # Recupera Shipping per ottenere id_carrier_api
        shipping_info = shipping_repo.get_carrier_info(id_shipping)
        carrier_api_id = shipping_info.id_carrier_api
        
        # Usa id_order dal documento invece del parametro
        order_id = order_doc.id_order
    else:
        # Comportamento esistente: usa Order.id_shipping
        id_shipping = or_repo.get_id_shipping_by_order_id(order_id)
        
        if not id_shipping:
            raise NotFoundException("Order", order_id, {"order_id": order_id, "reason": "Order has no shipping"})
        
        # Recupera Shipping per ottenere id_carrier_api
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
    # Passa id_shipping se disponibile (quando viene usato id_order_document)
    result = await shipment_service.create_shipment(order_id, id_shipping=id_shipping if 'id_shipping' in locals() else None)
    awb = result.get("awb", "") 
    # 4.1. Se id_order_document è presente, aggiorna il tracking dello shipping dell'OrderDocument
    # (i servizi aggiornano lo shipping dell'ordine, ma qui dobbiamo aggiornare quello del documento)
    if id_order_document and id_shipping:
        if awb:
            shipping_repo.update_tracking(id_shipping, awb)
    
    # 5. Emetti evento per creazione spedizione
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
                "source": "shipments.create_shipment",
                "id_order": order_id,
                "id_order_document": id_order_document if 'id_order_document' in locals() else None
            }
        )
        emit_event(event)
        logger.info(f"Event SHIPMENT_CREATED emitted for order {order_id}")
    except Exception as e:
        # Non bloccare la risposta in caso di errori nell'emissione dell'evento
        logger.warning(f"Failed to emit SHIPMENT_CREATED event for order {order_id}: {str(e)}", exc_info=True)
    
    # 6. Aggiorna stato ordine in base al flag is_multishipping
    try:
        order_service = OrderService(or_repo)
        order = or_repo.get_by_id(order_id)
        
        if order.is_multishipping == 0:
            # Spedizione normale -> sempre stato 4
            await order_service.update_order_status(order_id, 4)
            logger.info(f"Order {order_id} status updated to 4 (Spedizione Confermata) after shipment creation")
        else:
            # Multispedizione -> verifica se tutto spedito
            all_shipped = await shipping_service.check_all_products_shipped(order_id, db)
            if all_shipped:
                await order_service.update_order_status(order_id, 4)  # SPEDIZIONE CONFERMATA
                logger.info(f"Order {order_id} status updated to 4 (Spedizione Confermata) - all products shipped")
            else:
                await order_service.update_order_status(order_id, 7)  # MULTISPEDIZIONE
                logger.info(f"Order {order_id} status updated to 7 (Multispedizione) - not all products shipped")
    except Exception as e:
        # Non bloccare la risposta in caso di errori nell'aggiornamento dello stato
        logger.warning(f"Failed to update order {order_id} status: {str(e)}", exc_info=True)
    
    return result


@router.post("/bulk-create", response_model=BulkShipmentCreateResponseSchema)
async def bulk_create_shipments(
    request: BulkShipmentCreateRequestSchema = Body(...),
    or_repo: IOrderRepository = Depends(get_repository),
    shipping_repo: IShippingRepository = Depends(get_shipping_repository),
    shipping_service: IShippingService = Depends(get_shipping_service),
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
    
    
    successful = []
    failed = []
    total = len(request.order_ids)
    
    logger.info(f"Starting bulk shipment creation for {total} orders")
    
    for order_id in request.order_ids:
        try:
            # 1. Recupera id_shipping da Order
            id_shipping = or_repo.get_id_shipping_by_order_id(order_id)
            
            if not id_shipping:
                failed.append(BulkShipmentCreateError(
                    order_id=order_id,
                    error_type="NOT_FOUND",
                    error_message=f"Order {order_id} has no shipping"
                ))
                logger.warning(f"Order {order_id}: No shipping found")
                continue
            
            # 2. Recupera Shipping per ottenere id_carrier_api
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
            
            # Aggiorna stato ordine in base al flag is_multishipping
            # Il service gestisce le eccezioni internamente
            order_service = OrderService(or_repo)
            order = or_repo.get_by_id(order_id)
            
            if order.is_multishipping == 0:
                # Spedizione normale -> sempre stato 4
                await order_service.update_order_status(order_id, 4)
                logger.info(f"Order {order_id} status updated to 4 (Spedizione Confermata) after shipment creation")
            else:
                # Multispedizione -> verifica se tutto spedito
                all_shipped = await shipping_service.check_all_products_shipped(order_id, db)
                if all_shipped:
                    await order_service.update_order_status(order_id, 4)  # SPEDIZIONE CONFERMATA
                    logger.info(f"Order {order_id} status updated to 4 (Spedizione Confermata) - all products shipped")
                else:
                    await order_service.update_order_status(order_id, 7)  # MULTISPEDIZIONE
                    logger.info(f"Order {order_id} status updated to 7 (Multispedizione) - not all products shipped")

        except (NotFoundException, BusinessRuleException, ValidationException, 
                AuthenticationException, InfrastructureException) as e:
            # Mapping tra eccezioni e configurazioni di errore
            error_config = {
                NotFoundException: ("NOT_FOUND", "not_found", logger.warning),
                BusinessRuleException: ("BUSINESS_RULE_ERROR", "business", logger.warning),
                ValidationException: ("VALIDATION_ERROR", "validation", logger.warning),
                AuthenticationException: ("AUTHENTICATION_ERROR", "authentication", logger.warning),
                InfrastructureException: ("INFRASTRUCTURE_ERROR", "infrastructure", logger.warning)
            }
            
            error_type, default_category, log_func = error_config[type(e)]
            failed.append(_create_bulk_shipment_error(order_id, e, error_type, default_category))
            log_func(f"Order {order_id}: {type(e).__name__} - {str(e)}")
            
        except Exception as e:
            # Gestione generica per tutte le altre eccezioni
            failed.append(_create_bulk_shipment_error(
                order_id, 
                e, 
                "UNKNOWN_ERROR", 
                None
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
    carrier_repo: IApiCarrierRepository = Depends(get_carrier_repository),
    shipping_repo: IShippingRepository = Depends(get_shipping_repository),
    shipping_service: IShippingService = Depends(get_shipping_service),
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
    
    result = await tracking_service.get_tracking(tracking_list, id_carrier_api)
    
    # Aggiorna lo stato shipment in base al tracking (se presente)
    # Il service gestisce le eccezioni internamente
    carrier = carrier_repo.get_by_id(id_carrier_api)
    carrier_type = carrier.carrier_type.value if carrier else None
    
    await shipping_service.sync_shipping_states_from_tracking_results(
        result,
        carrier_type=carrier_type
    )
    
    return result


@router.get("/download-label/{awb}")
async def download_shipment_label(
    awb: str,
    user: dict = Depends(get_current_user),
    shipment_document_repo: IShipmentDocumentRepository = Depends(get_shipment_document_repository),
    shipping_repo: IShippingRepository = Depends(get_shipping_repository),
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
    documents = shipment_document_repo.get_by_awb(awb)
    
    carrier_api_id = None
    if documents:
        carrier_api_id = documents[0].carrier_api_id
    
    # 2. Se non trovato, cerca in Shipping.tracking
    if not carrier_api_id:
        carrier_api_id = shipping_repo.get_carrier_id_by_tracking(awb)
    
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
    shipping_repo: IShippingRepository = Depends(get_shipping_repository),
    order_repo: IOrderRepository = Depends(get_repository),
    shipping_service: IShippingService = Depends(get_shipping_service),
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
    order = order_repo.get_by_id_or_raise(order_id)
    # 2. Recupera Shipping per ottenere id_carrier_api
    shipping_info = shipping_repo.get_carrier_info(order.id_shipping)
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
    
    # 5. Dopo l'annullamento, verifica se ci sono ancora spedizioni attive
    # usando la funzione del service (che usa il repository)
    active_count = shipping_service.get_active_shipments_count(order_id)
    
    if active_count == 0:
        # Nessuna spedizione attiva -> reset flag is_multishipping
        order_repo.set_multishipping(order_id, 0)
        logger.info(f"Reset is_multishipping flag for order {order_id} - no active shipments")
    
    return result


@router.post("/create-multi-shipments", response_model=MultiShippingDocumentResponseSchema)
async def create_multi_shipments(
    request: MultiShippingDocumentCreateRequestSchema,
    user: dict = Depends(get_current_user),
    shipping_repo: IShippingRepository = Depends(get_shipping_repository),
    shipping_service: IShippingService = Depends(get_shipping_service),
    db: Session = Depends(get_db)
):
    """
    Crea un documento di spedizione multipla con articoli selezionati.
    
    Crea un OrderDocument con type_document="shipping" e un Shipping associato,
    permettendo di spedire solo alcuni prodotti dell'ordine con un corriere specifico.
    
    Args:
        request: Dati per creare il documento spedizione
        user: Utente autenticato
        db: Database session
        
    Returns:
        MultiShippingDocumentResponseSchema con dati idratati
    """
    return await shipping_service.create_multi_shipment(request, user.get("id", 0), db)


@router.get("/orders/{order_id}/shipment-status", response_model=OrderShipmentStatusResponseSchema)
async def get_order_shipment_status(
    order_id: int = Path(..., description="ID dell'ordine"),
    user: dict = Depends(get_current_user),
    shipping_repo: IShippingRepository = Depends(get_shipping_repository),
    db: Session = Depends(get_db)
):
    """
    Recupera lo stato di spedizione per ogni articolo dell'ordine.
    
    Mostra per ogni prodotto:
    - Quantità totale nell'ordine
    - Quantità già spedita
    - Quantità rimanente da spedire
    
    Args:
        order_id: ID dell'ordine
        user: Utente autenticato
        db: Database session
        
    Returns:
        OrderShipmentStatusResponseSchema con stato per ogni articolo
    """
    shipping_service = ShippingService(shipping_repo)
    return await shipping_service.get_order_shipment_status(order_id, db)


@router.get("/orders/{order_id}/multi-shipments", response_model=MultiShippingDocumentListResponseSchema)
async def get_order_multi_shipments(
    order_id: int = Path(..., description="ID dell'ordine"),
    user: dict = Depends(get_current_user),
    shipping_service: IShippingService = Depends(get_shipping_service),
    db: Session = Depends(get_db)
):
    """
    Recupera lista di spedizioni multiple per un ordine.
    
    Restituisce tutti gli OrderDocument con type_document="shipping" per l'ordine specificato.
    
    Args:
        order_id: ID dell'ordine
        user: Utente autenticato
        db: Database session
        
    Returns:
        MultiShippingDocumentListResponseSchema con lista spedizioni
    """
    return await shipping_service.get_multi_shipments_by_order(order_id, db)
