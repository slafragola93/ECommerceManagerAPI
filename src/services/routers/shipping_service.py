"""
Shipping Service rifattorizzato seguendo i principi SOLID con gestione errori intelligente
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, NoResultFound

from src.core.exceptions import (
    BusinessRuleException,
    ErrorCode,
    ExceptionFactory,
    NotFoundException,
    ValidationException,
    InfrastructureException,
    AlreadyExistsError
)
from src.events.core.event import EventType
from src.events.decorators import emit_event_on_success
from src.events.extractors import extract_shipping_status_changed_data
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.order_document import OrderDocument
from src.models.order_package import OrderPackage
from src.models.shipping import Shipping
from src.repository.interfaces.shipping_repository_interface import IShippingRepository
from src.repository.order_detail_repository import OrderDetailRepository
from src.repository.order_repository import OrderRepository
from src.repository.tax_repository import TaxRepository
from src.schemas.shipping_schema import (
    MultiShippingDocumentCreateRequestSchema,
    MultiShippingDocumentItemResponseSchema,
    MultiShippingDocumentListItemSchema,
    MultiShippingDocumentListResponseSchema,
    MultiShippingDocumentPackageResponseSchema,
    MultiShippingDocumentResponseSchema,
    OrderShipmentStatusItemSchema,
    OrderShipmentStatusResponseSchema,
    ShippingSchema,
    ShippingUpdateSchema,
)
from src.services.interfaces.shipping_service_interface import IShippingService


class ShippingService(IShippingService):
    """Shipping Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP con gestione errori intelligente"""
    
    def __init__(self, shipping_repository: IShippingRepository):
        self._shipping_repository = shipping_repository
        
    async def create_shipping(self, shipping_data: ShippingSchema) -> Shipping:
        """Crea un nuovo shipping con validazioni business e gestione errori specifica"""
        
        try:
            # Validazione dei dati di input
            if not shipping_data:
                raise ExceptionFactory.required_field_missing("shipping_data")
            
            # Crea il shipping
            shipping = Shipping(**shipping_data.model_dump())
            shipping = self._shipping_repository.create(shipping)
            return shipping
            
        except IntegrityError as e:
            # Violazione constraint database (es. duplicate key, foreign key)
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                raise AlreadyExistsError(
                    f"Shipping with these parameters already exists",
                    "Shipping",
                    details={"constraint_violation": str(e)}
                )
            else:
                raise InfrastructureException(
                    f"Database constraint violation: {str(e)}",
                    ErrorCode.DATABASE_ERROR,
                    details={"sql_error": str(e)}
                )
                
        except SQLAlchemyError as e:
            # Altri errori SQLAlchemy
            raise InfrastructureException(
                f"Database error while creating shipping: {str(e)}",
                ErrorCode.DATABASE_ERROR,
                details={"sql_error": str(e)}
            )
            
        except (ValidationException, BusinessRuleException, NotFoundException) as e:
            # Rilancia le eccezioni custom così come sono
            raise
            
        except Exception as e:
            # Cattura errori imprevisti
            raise InfrastructureException(
                f"Unexpected error creating shipping: {str(e)}",
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                details={"original_error": str(e)}
            )
    
    def _should_emit_shipping_status_event(*args, result=None, **kwargs) -> bool:
        """Verifica se l'evento di cambio stato shipping deve essere emesso."""
        if not isinstance(result, dict):
            return False
        old_state_id = result.get("old_state_id")
        new_state_id = result.get("new_state_id")
        return old_state_id is not None and new_state_id is not None and old_state_id != new_state_id
    
    def _extract_shipping_update_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
        """Estrae i dati dell'evento di cambio stato shipping da update_shipping."""
        if not isinstance(result, dict):
            return None
        return {
            "id_shipping": result.get("id_shipping"),
            "old_state_id": result.get("old_state_id"),
            "new_state_id": result.get("new_state_id"),
        }
    
    @emit_event_on_success(
        event_type=EventType.SHIPPING_STATUS_CHANGED,
        data_extractor=extract_shipping_status_changed_data,
        condition=_should_emit_shipping_status_event,
        source="shipping_service.update_shipping",
    )
    async def update_shipping(self, shipping_id: int, shipping_data: ShippingUpdateSchema) -> Dict[str, Any]:
        """Aggiorna un shipping esistente con gestione errori intelligente"""
        
        try:
            # Validazioni input
            if shipping_id <= 0:
                raise ValidationException(
                    "Invalid shipping ID",
                    ErrorCode.VALIDATION_ERROR,
                    details={"shipping_id": shipping_id}
                )
            
            if not shipping_data:
                raise ExceptionFactory.required_field_missing("shipping_data")
            
            # Verifica esistenza - usa il metodo del repository che già lancia NotFoundException
            shipping = self._shipping_repository.get_by_id_or_raise(shipping_id)
            
            # Salva vecchio stato prima dell'aggiornamento
            old_state_id = shipping.id_shipping_state
            
            # Validazione business rules se applicabile
            update_data = shipping_data.model_dump(exclude_unset=True)
            if not update_data:
                raise ValidationException(
                    "No valid fields provided for update",
                    ErrorCode.VALIDATION_ERROR,
                    details={"provided_data": str(shipping_data)}
                )
            
            # Aggiorna i campi
            for field_name, value in update_data.items():
                if hasattr(shipping, field_name):
                    setattr(shipping, field_name, value)
                else:
                    raise ValidationException(
                        f"Invalid field '{field_name}' for shipping update",
                        ErrorCode.VALIDATION_ERROR,
                        details={"invalid_field": field_name}
                    )
            
            updated_shipping = self._shipping_repository.update(shipping)
            
            # Restituisce dict per evento se stato è cambiato
            new_state_id = updated_shipping.id_shipping_state
            if old_state_id != new_state_id:
                return {
                    "id_shipping": shipping_id,
                    "old_state_id": old_state_id,
                    "new_state_id": new_state_id,
                    "shipping": updated_shipping
                }
            
            return {
                "id_shipping": shipping_id,
                "shipping": updated_shipping
            }
            
        except IntegrityError as e:
            raise InfrastructureException(
                f"Database constraint violation during update: {str(e)}",
                ErrorCode.DATABASE_ERROR,
                details={"shipping_id": shipping_id, "sql_error": str(e)}
            )
            
        except SQLAlchemyError as e:
            raise InfrastructureException(
                f"Database error while updating shipping {shipping_id}: {str(e)}",
                ErrorCode.DATABASE_ERROR,
                details={"shipping_id": shipping_id, "sql_error": str(e)}
            )
            
        except (ValidationException, BusinessRuleException, NotFoundException) as e:
            # Rilancia le eccezioni custom così come sono
            raise
            
        except Exception as e:
            raise InfrastructureException(
                f"Unexpected error updating shipping {shipping_id}: {str(e)}",
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                details={"shipping_id": shipping_id, "original_error": str(e)}
            )
    
    async def get_shipping(self, shipping_id: int) -> Shipping:
        """Ottiene un shipping per ID con gestione errori"""
        try:
            if shipping_id <= 0:
                raise ValidationException(
                    "Invalid shipping ID",
                    ErrorCode.VALIDATION_ERROR,
                    details={"shipping_id": shipping_id}
                )
            
            shipping = self._shipping_repository.get_by_id_or_raise(shipping_id)
            return shipping
            
        except (ValidationException, NotFoundException) as e:
            # Rilancia le eccezioni custom così come sono
            raise
            
        except SQLAlchemyError as e:
            raise InfrastructureException(
                f"Database error while retrieving shipping {shipping_id}: {str(e)}",
                ErrorCode.DATABASE_ERROR,
                details={"shipping_id": shipping_id, "sql_error": str(e)}
            )
            
        except Exception as e:
            raise InfrastructureException(
                f"Unexpected error retrieving shipping {shipping_id}: {str(e)}",
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                details={"shipping_id": shipping_id, "original_error": str(e)}
            )
    
    async def get_shippings(self, page: int = 1, limit: int = 10, **filters) -> List[Shipping]:
        """Ottiene la lista dei shipping con filtri e gestione errori intelligente"""
        try:
            # Validazione parametri
            if page < 1:
                page = 1
            if limit < 1:
                limit = 10
            if limit > 1000:  # Protezione contro query troppo grandi
                raise ValidationException(
                    "Limit too high, maximum allowed is 1000",
                    ErrorCode.VALIDATION_ERROR,
                    details={"provided_limit": limit, "max_limit": 1000}
                )
            
            # Aggiungi page e limit ai filtri
            filters['page'] = page
            filters['limit'] = limit
            
            # Usa il repository con i filtri
            shippings = self._shipping_repository.get_all(**filters)
            
            return shippings
            
        except ValidationException as e:
            # Rilancia eccezioni di validazione
            raise
            
        except SQLAlchemyError as e:
            raise InfrastructureException(
                f"Database error while retrieving shippings: {str(e)}",
                ErrorCode.DATABASE_ERROR,
                details={"filters": filters, "sql_error": str(e)}
            )
            
        except Exception as e:
            raise InfrastructureException(
                f"Unexpected error retrieving shippings: {str(e)}",
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                details={"filters": filters, "original_error": str(e)}
            )
    
    async def delete_shipping(self, shipping_id: int) -> bool:
        """Elimina un shipping con gestione errori completa"""
        try:
            if shipping_id <= 0:
                raise ValidationException(
                    "Invalid shipping ID",
                    ErrorCode.VALIDATION_ERROR,
                    details={"shipping_id": shipping_id}
                )
            
            # Verifica esistenza
            self._shipping_repository.get_by_id_or_raise(shipping_id)
            
            # Verifica business rules per cancellazione
            # (es. non si può cancellare se ha ordini associati)
            # Qui potresti aggiungere logica specifica
            
            return self._shipping_repository.delete(shipping_id)
            
        except IntegrityError as e:
            # Errore di foreign key constraint (shipping ha dipendenze)
            raise BusinessRuleException(
                f"Cannot delete shipping {shipping_id}: has associated records",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                details={"shipping_id": shipping_id, "constraint_error": str(e)}
            )
            
        except SQLAlchemyError as e:
            raise InfrastructureException(
                f"Database error while deleting shipping {shipping_id}: {str(e)}",
                ErrorCode.DATABASE_ERROR,
                details={"shipping_id": shipping_id, "sql_error": str(e)}
            )
            
        except (ValidationException, BusinessRuleException, NotFoundException) as e:
            # Rilancia le eccezioni custom così come sono
            raise
            
        except Exception as e:
            raise InfrastructureException(
                f"Unexpected error deleting shipping {shipping_id}: {str(e)}",
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                details={"shipping_id": shipping_id, "original_error": str(e)}
            )
    
    async def get_shippings_count(self, **filters) -> int:
        """Ottiene il numero totale di shipping con filtri e gestione errori"""
        try:
            # Usa il repository con i filtri
            return self._shipping_repository.get_count(**filters)
            
        except SQLAlchemyError as e:
            raise InfrastructureException(
                f"Database error while counting shippings: {str(e)}",
                ErrorCode.DATABASE_ERROR,
                details={"filters": filters, "sql_error": str(e)}
            )
            
        except Exception as e:
            raise InfrastructureException(
                f"Unexpected error counting shippings: {str(e)}",
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                details={"filters": filters, "original_error": str(e)}
            )
    
    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Shipping"""
        try:
            # Implementa qui le validazioni specifiche per il tuo business
            # Es: validazione stati, carrier, indirizzi, ecc.
            pass
            
        except Exception as e:
            raise BusinessRuleException(
                f"Business rule validation failed: {str(e)}",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                details={"validation_data": str(data), "original_error": str(e)}
            )
    
    async def create_multi_shipment(
        self,
        request: MultiShippingDocumentCreateRequestSchema,
        user_id: int,
        db: Session
    ) -> MultiShippingDocumentResponseSchema:
        """
        Crea un documento di spedizione multipla con gestione errori completa
        """
        try:
            # Validazioni iniziali
            if not request:
                raise ExceptionFactory.required_field_missing("request")
            
            if user_id <= 0:
                raise ValidationException(
                    "Invalid user ID",
                    ErrorCode.VALIDATION_ERROR,
                    details={"user_id": user_id}
                )
            
            if not request.items or len(request.items) == 0:
                raise ValidationException(
                    "At least one item is required for multi-shipment",
                    ErrorCode.REQUIRED_FIELD_MISSING,
                    details={"items_count": len(request.items) if request.items else 0}
                )
            
            # Verifica esistenza ordine
            order = db.query(Order).filter(Order.id_order == request.id_order).first()
            if not order:
                raise ExceptionFactory.order_not_found(request.id_order)
            
            # Verifica business rules
            if request.id_carrier_api and request.id_carrier_api <= 0:
                raise ValidationException(
                    "Invalid carrier API ID",
                    ErrorCode.VALIDATION_ERROR,
                    details={"id_carrier_api": request.id_carrier_api}
                )
            
            tax_repository = TaxRepository(db)
            order_detail_repository = OrderDetailRepository(db)
            order_repository = OrderRepository(db)
            
            # 1. Valida ordine esistente
            order = order_repository.get_by_id_or_raise(request.id_order)
            if not order:
                raise NotFoundException("Order", request.id_order)
            
            # 2. Determina indirizzo di consegna
            id_address_delivery = request.id_address_delivery or order.id_address_delivery
            
            # 3. Valida quantità disponibili (non già spedite)
            for item in request.items:
                order_detail = order_detail_repository.get_by_order_detail_and_order(item.id_order_detail, request.id_order)
                
                if not order_detail:
                    raise NotFoundException(
                        "OrderDetail", 
                        item.id_order_detail,
                        {"order_id": request.id_order}
                    )
                
                # Calcola quantità già spedita in altri OrderDocument type=shipping
                shipped_qty = self._shipping_repository.get_shipped_quantity_by_product(
                    id_order=request.id_order,
                    id_product=order_detail.id_product,
                    product_reference=order_detail.product_reference
                )

                available_qty = order_detail.product_qty - shipped_qty
                if item.quantity > available_qty:
                    raise BusinessRuleException(
                        f"Cannot ship {item.quantity} units of product {order_detail.product_name}. "
                        f"Only {available_qty} available (already shipped: {shipped_qty})",
                        details={
                            "id_order_detail": item.id_order_detail,
                            "requested_quantity": item.quantity,
                            "available_quantity": available_qty,
                            "already_shipped": shipped_qty
                        }
                    )
            
            # 4. Crea Shipping con id_carrier_api
            shipping_data = {
                "id_carrier_api": request.id_carrier_api,
                "id_shipping_state": 1,  # Stato iniziale: "In preparazione"
                "weight": 0.0,  # Verrà calcolato dai packages
                "price_tax_incl": 0.0,
                "price_tax_excl": 0.0,
                "shipping_message": request.shipping_message
            }
            new_id_shipping = self._shipping_repository.create_and_get_id(shipping_data)
  
            
            # 5. Genera numero documento automaticamente
            from src.services.routers.order_document_service import OrderDocumentService
            order_doc_service = OrderDocumentService(db)
            document_number = order_doc_service.get_next_document_number("SHIP")
            print(f"document_number: {document_number}")
            # 6. Crea OrderDocument(type_document="shipping", id_shipping=...)
            new_order_doc = OrderDocument(
                type_document="shipping",
                document_number=document_number,
                id_order=request.id_order,
                id_store=order.id_store,
                id_address_delivery=id_address_delivery,
                id_customer=order.id_customer,
                id_shipping=new_id_shipping,
                total_weight=0.0,  # Verrà ricalcolato
                total_price_with_tax=0.0,  # Verrà ricalcolato
                total_price_net=0.0,  # Verrà ricalcolato
                products_total_price_net=0.0,  # Verrà ricalcolato
                products_total_price_with_tax=0.0,  # Verrà ricalcolato
                note=f"Spedizione multipla creata da ordine {order.reference or request.id_order}",
                date_add=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(new_order_doc)
            db.flush()  # Per ottenere id_order_document
            
            # 7. Copia OrderDetail selezionati con quantità
            total_weight = 0.0
            for item in request.items:
                original_detail = order_detail_repository.get_first_order_detail_by_id(item.id_order_detail)
                
                if not original_detail:
                    raise NotFoundException(
                        "OrderDetail",
                        item.id_order_detail,
                        details={"id_order": request.id_order}
                    )
                
                # Calcola prezzi unitari (devono essere al pezzo singolo)
                unit_price_net = float(original_detail.unit_price_net) if original_detail.unit_price_net else 0.0
                unit_price_with_tax = float(original_detail.unit_price_with_tax) if original_detail.unit_price_with_tax else 0.0
                
                # Calcola totali per la quantità specificata
                total_price_net = unit_price_net * item.quantity
                total_price_with_tax = unit_price_with_tax * item.quantity
                
                # Applica sconti se presenti
                reduction_percent = float(original_detail.reduction_percent) if original_detail.reduction_percent else 0.0
                reduction_amount = float(original_detail.reduction_amount) if original_detail.reduction_amount else 0.0
                
                if reduction_percent > 0:
                    from src.services.core.tool import calculate_amount_with_percentage
                    discount = calculate_amount_with_percentage(total_price_net, reduction_percent)
                    total_price_net = total_price_net - discount
                    # Ricalcola total_price_with_tax dopo lo sconto
                    if original_detail.id_tax:
                        tax = tax_repository.get_tax_by_id(original_detail.id_tax)
                        if tax and tax.percentage is not None:
                            tax_percentage = float(tax.percentage)
                            from src.services.core.tool import calculate_price_with_tax
                            total_price_with_tax = calculate_price_with_tax(total_price_net, tax_percentage, quantity=1)
                elif reduction_amount > 0:
                    total_price_net = total_price_net - reduction_amount
                    # Ricalcola total_price_with_tax dopo lo sconto
                    if original_detail.id_tax:
                        tax = tax_repository.get_tax_by_id(original_detail.id_tax)
                        if tax and tax.percentage is not None:
                            tax_percentage = float(tax.percentage)
                            from src.services.core.tool import calculate_price_with_tax
                            total_price_with_tax = calculate_price_with_tax(total_price_net, tax_percentage, quantity=1)
                
                # Crea OrderDetail nel documento
                new_detail = OrderDetail(
                    id_origin=0,
                    id_order=0,  # Per distinguere dalle righe ordine
                    id_order_document=new_order_doc.id_order_document,
                    id_product=original_detail.id_product,
                    product_name=original_detail.product_name,
                    product_reference=original_detail.product_reference,
                    product_qty=item.quantity,
                    product_weight=original_detail.product_weight,
                    unit_price_net=unit_price_net,
                    unit_price_with_tax=unit_price_with_tax,
                    total_price_net=total_price_net,
                    total_price_with_tax=total_price_with_tax,
                    id_tax=original_detail.id_tax,
                    reduction_percent=reduction_percent,
                    reduction_amount=reduction_amount,
                    rda=original_detail.rda if hasattr(original_detail, 'rda') else None,
                    rda_quantity=original_detail.rda_quantity if hasattr(original_detail, 'rda_quantity') and original_detail.rda_quantity is not None else None,
                    note=original_detail.note
                )
                db.add(new_detail)
                
                # Accumula peso
                product_weight = float(original_detail.product_weight) if original_detail.product_weight else 0.0
                total_weight += product_weight * item.quantity
            
            # 8. Crea OrderPackage se forniti
            if request.packages:
                for pkg in request.packages:
                    package = OrderPackage(
                        id_order_document=new_order_doc.id_order_document,
                        height=pkg.height,
                        width=pkg.width,
                        depth=pkg.depth,
                        length=pkg.length,
                        weight=pkg.weight,
                        value=0.0
                    )
                    db.add(package)
                    # Se il peso non è già stato calcolato dagli articoli, usa quello dei packages
                    if total_weight == 0.0:
                        total_weight += pkg.weight
            
            # 9. Aggiorna peso shipping
            # Recupera lo shipping dal database per aggiornare il peso
            shipping = self._shipping_repository.get_by_id(new_id_shipping)
            if shipping:
                shipping.weight = total_weight
                self._shipping_repository.update(shipping)
            
            # 10. Ricalcola totali documento
            order_doc_service.update_document_totals(new_order_doc.id_order_document, "shipping")
            
            db.commit()
            
            # Ricarica con relazioni per risposta
            order_doc = db.query(OrderDocument).options(
                joinedload(OrderDocument.shipping),
                selectinload(OrderDocument.order_packages)
            ).filter(
                OrderDocument.id_order_document == new_order_doc.id_order_document
            ).first()
            
            # Carica OrderDetails
            details = db.query(OrderDetail).filter(
                OrderDetail.id_order_document == new_order_doc.id_order_document,
                OrderDetail.id_order == 0
            ).all()
            
            # Costruisci risposta
            return MultiShippingDocumentResponseSchema(
                id_order_document=order_doc.id_order_document,
                id_shipping=order_doc.id_shipping,
                document_number=order_doc.document_number,
                type_document=order_doc.type_document,
                id_order=order_doc.id_order,
                id_carrier_api=order_doc.shipping.id_carrier_api if order_doc.shipping else None,
                id_address_delivery=order_doc.id_address_delivery,
                items=[
                    MultiShippingDocumentItemResponseSchema(
                        id_order_detail=d.id_order_detail,
                        product_name=d.product_name,
                        product_reference=d.product_reference,
                        quantity=d.product_qty,
                        unit_price_net=float(d.unit_price_net) if d.unit_price_net else 0.0,
                        unit_price_with_tax=float(d.unit_price_with_tax) if d.unit_price_with_tax else 0.0,
                        total_price_net=float(d.total_price_net) if d.total_price_net else 0.0,
                        total_price_with_tax=float(d.total_price_with_tax) if d.total_price_with_tax else 0.0,
                        product_weight=float(d.product_weight) if d.product_weight else 0.0
                    )
                    for d in details
                ],
                packages=[
                    MultiShippingDocumentPackageResponseSchema(
                        id_order_package=p.id_order_package,
                        height=float(p.height) if p.height else None,
                        width=float(p.width) if p.width else None,
                        depth=float(p.depth) if p.depth else None,
                        length=float(p.length) if p.length else None,
                        weight=float(p.weight) if p.weight else 0.0,
                        value=float(p.value) if p.value else None
                    )
                    for p in order_doc.order_packages
                ],
                total_weight=float(order_doc.total_weight) if order_doc.total_weight else None,
                total_price_with_tax=float(order_doc.total_price_with_tax) if order_doc.total_price_with_tax else None,
                total_price_net=float(order_doc.total_price_net) if order_doc.total_price_net else None,
                products_total_price_net=float(order_doc.products_total_price_net) if order_doc.products_total_price_net else None,
                products_total_price_with_tax=float(order_doc.products_total_price_with_tax) if order_doc.products_total_price_with_tax else None,
                shipping_message=order_doc.shipping.shipping_message if order_doc.shipping else None,
                date_add=order_doc.date_add.isoformat() if order_doc.date_add else ""
            )
            
        except IntegrityError as e:
            db.rollback()
            if "duplicate" in str(e).lower():
                raise AlreadyExistsError(
                    "Multi-shipment document with this number already exists",
                    "MultiShippingDocument",
                    details={"document_number": document_number, "sql_error": str(e)}
                )
            else:
                raise InfrastructureException(
                    f"Database constraint violation: {str(e)}",
                    ErrorCode.DATABASE_ERROR,
                    details={"request": str(request), "sql_error": str(e)}
                )
                
        except SQLAlchemyError as e:
            db.rollback()
            raise InfrastructureException(
                f"Database error while creating multi-shipment: {str(e)}",
                ErrorCode.DATABASE_ERROR,
                details={"request": str(request), "sql_error": str(e)}
            )
            
        except (NotFoundException, BusinessRuleException, ValidationException) as e:
            db.rollback()
            # Rilancia le eccezioni custom così come sono
            raise
            
        except Exception as e:
            # Cattura tutte le altre eccezioni e le converte
            db.rollback()
            raise InfrastructureException(
                f"Unexpected error creating multi-shipment: {str(e)}",
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                details={"request": str(request), "original_error": str(e)}
            )

    async def get_order_shipment_status(
        self,
        order_id: int,
        db: Session
    ) -> OrderShipmentStatusResponseSchema:
        """
        Calcola lo stato di spedizione per ogni articolo dell'ordine con gestione errori
        """
        try:
            # Validazione input
            if order_id <= 0:
                raise ValidationException(
                    "Invalid order ID",
                    ErrorCode.VALIDATION_ERROR,
                    details={"order_id": order_id}
                )
            
            # Verifica ordine esistente
            order = db.query(Order).filter(Order.id_order == order_id).first()
            if not order:
                raise ExceptionFactory.order_not_found(order_id)
            
            # Recupera tutti gli OrderDetail dell'ordine
            order_details = db.query(OrderDetail).filter(
                OrderDetail.id_order == order_id,
                OrderDetail.id_order_document.is_(None)  # Solo righe ordine, non documento
            ).all()
            
            if not order_details:
                raise NotFoundException(
                    "OrderDetails",
                    details={"id_order": order_id, "message": "No order details found for this order"}
                )
            
            items = []
            all_shipped = True
            
            for detail in order_details:
                try:
                    # Calcola quantità già spedita in OrderDocument type=shipping
                    shipped_qty = db.query(func.coalesce(func.sum(OrderDetail.product_qty), 0)).join(
                        OrderDocument, OrderDetail.id_order_document == OrderDocument.id_order_document
                    ).filter(
                        OrderDocument.type_document == "shipping",
                        OrderDocument.id_order == order_id,
                        OrderDetail.id_order == 0,  # Solo righe documento
                        OrderDetail.id_product == detail.id_product,
                        OrderDetail.product_reference == detail.product_reference
                    ).scalar()
                    
                    total_qty = detail.product_qty
                    remaining_qty = total_qty - shipped_qty
                    fully_shipped = remaining_qty <= 0
                    
                    if not fully_shipped:
                        all_shipped = False
                    
                    items.append(OrderShipmentStatusItemSchema(
                        id_order_detail=detail.id_order_detail,
                        product_name=detail.product_name,
                        product_reference=detail.product_reference,
                        total_qty=total_qty,
                        shipped_qty=int(shipped_qty),
                        remaining_qty=remaining_qty,
                        fully_shipped=fully_shipped
                    ))
                    
                except SQLAlchemyError as e:
                    # Errore specifico per questo detail
                    raise InfrastructureException(
                        f"Database error calculating shipment status for detail {detail.id_order_detail}: {str(e)}",
                        ErrorCode.DATABASE_ERROR,
                        details={
                            "order_id": order_id,
                            "order_detail_id": detail.id_order_detail,
                            "sql_error": str(e)
                        }
                    )
            
            return OrderShipmentStatusResponseSchema(
                order_id=order_id,
                items=items,
                all_shipped=all_shipped
            )
            
        except SQLAlchemyError as e:
            raise InfrastructureException(
                f"Database error retrieving shipment status for order {order_id}: {str(e)}",
                ErrorCode.DATABASE_ERROR,
                details={"order_id": order_id, "sql_error": str(e)}
            )
            
        except (ValidationException, NotFoundException) as e:
            # Rilancia le eccezioni custom così come sono
            raise
            
        except Exception as e:
            raise InfrastructureException(
                f"Unexpected error retrieving shipment status for order {order_id}: {str(e)}",
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                details={"order_id": order_id, "original_error": str(e)}
            )
    
    async def get_multi_shipments_by_order(
        self,
        order_id: int,
        db: Session
    ) -> MultiShippingDocumentListResponseSchema:
        """
        Recupera lista di spedizioni multiple per un ordine con gestione errori completa
        """
        try:
            # Validazione input
            if order_id <= 0:
                raise ValidationException(
                    "Invalid order ID",
                    ErrorCode.VALIDATION_ERROR,
                    details={"order_id": order_id}
                )
            
            # Verifica ordine esistente
            order = db.query(Order).filter(Order.id_order == order_id).first()
            if not order:
                raise ExceptionFactory.order_not_found(order_id)
            
            # Query idratata per OrderDocument type=shipping
            shipments = db.query(OrderDocument).options(
                joinedload(OrderDocument.shipping),
                selectinload(OrderDocument.order_packages)
            ).filter(
                OrderDocument.id_order == order_id,
                OrderDocument.type_document == "shipping"
            ).all()
            
            shipment_list = []
            for shipment in shipments:
                try:
                    # Conta items
                    items_count = db.query(func.count(OrderDetail.id_order_detail)).filter(
                        OrderDetail.id_order_document == shipment.id_order_document,
                        OrderDetail.id_order == 0
                    ).scalar()
                    
                    shipment_list.append(MultiShippingDocumentListItemSchema(
                        id_order_document=shipment.id_order_document,
                        id_shipping=shipment.id_shipping,
                        document_number=shipment.document_number,
                        id_carrier_api=shipment.shipping.id_carrier_api if shipment.shipping else None,
                        total_weight=float(shipment.total_weight) if shipment.total_weight else None,
                        date_add=shipment.date_add.isoformat() if shipment.date_add else "",
                        items_count=items_count or 0,
                        packages_count=len(shipment.order_packages)
                    ))
                    
                except SQLAlchemyError as e:
                    # Errore specifico per questa spedizione - log e continua
                    raise InfrastructureException(
                        f"Database error processing shipment {shipment.id_order_document}: {str(e)}",
                        ErrorCode.DATABASE_ERROR,
                        details={
                            "order_id": order_id,
                            "shipment_id": shipment.id_order_document,
                            "sql_error": str(e)
                        }
                    )
            
            return MultiShippingDocumentListResponseSchema(
                order_id=order_id,
                shipments=shipment_list,
                total=len(shipment_list)
            )
            
        except SQLAlchemyError as e:
            raise InfrastructureException(
                f"Database error retrieving multi-shipments for order {order_id}: {str(e)}",
                ErrorCode.DATABASE_ERROR,
                details={"order_id": order_id, "sql_error": str(e)}
            )
            
        except (ValidationException, NotFoundException) as e:
            # Rilancia le eccezioni custom così come sono
            raise
            
        except Exception as e:
            raise InfrastructureException(
                f"Unexpected error retrieving multi-shipments for order {order_id}: {str(e)}",
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                details={"order_id": order_id, "original_error": str(e)}
            )
    
    async def sync_shipping_states_from_tracking_results(
        self,
        tracking_results: List[Dict[str, Any]],
        carrier_type: Optional[str] = None
    ) -> int:
        """
        Sincronizza lo stato delle spedizioni dai risultati del tracking.
        
        Args:
            tracking_results: Lista di risultati normalizzati dal tracking service.
                Ogni risultato deve contenere:
                - tracking_number: str
                - current_internal_state_id: int
                - events: List[Dict] (opzionale, per estrarre event_code e description)
            carrier_type: Tipo carrier (BRT, DHL, FEDEX) per logging
            
        Returns:
            Numero di spedizioni aggiornate
        """
        updated_count = 0
        
        for result in tracking_results:
            try:
                tracking_number = result.get("tracking_number")
                if not tracking_number:
                    continue
                
                state_id = result.get("current_internal_state_id")
                if not state_id:
                    continue
                
                # Estrai informazioni dall'ultimo evento (se presente)
                event_code = None
                event_description = None
                events = result.get("events", [])
                if events:
                    # Prendi l'ultimo evento (più recente)
                    last_event = events[-1] if events else None
                    if last_event:
                        event_code = last_event.get("code")
                        event_description = last_event.get("description")
                
                # Aggiorna lo stato usando il repository
                rows_updated = self._shipping_repository.update_state_by_tracking(
                    tracking=tracking_number,
                    state_id=state_id,
                    carrier_type=carrier_type,
                    event_code=event_code,
                    event_description=event_description
                )
                
                if rows_updated > 0:
                    updated_count += 1
                    
            except Exception as e:
                # Log errore ma continua con gli altri risultati
                import logging
                logger = logging.getLogger(__name__)
                logger.error(
                    f"Error syncing shipping state for tracking {result.get('tracking_number', 'unknown')}: {str(e)}",
                    exc_info=True
                )
                continue
        
        return updated_count