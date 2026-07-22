"""
Servizio centralizzato per la gestione dei documenti fiscali
"""
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional, Tuple
from src.repository.interfaces.order_repository_interface import IOrderRepository
from src.repository.interfaces.order_detail_repository_interface import IOrderDetailRepository
from src.services.interfaces.fiscal_document_service_interface import IFiscalDocumentService
from src.repository.interfaces.fiscal_document_repository_interface import IFiscalDocumentRepository
from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.models.order import Order
from src.schemas.return_schema import ReturnCreateSchema, ReturnDocumentResponseSchema, ReturnDetailResponseSchema, ReturnResponseSchema, ReturnUpdateSchema, ReturnDetailUpdateSchema
from src.schemas.fiscal_document_schema import (
    CreditNoteEligibleLinesResponseSchema,
    InvoiceExportFiltersSchema,
    InvoiceExportFormatSchema,
    InvoiceListExportItemSchema,
    InvoiceResponseSchema,
)
from src.services.export.fiscal_document_export_service import FiscalDocumentExportService
from src.services.external.fatturapa_filename import (
    normalize_xml_bytes,
    resolve_fatturapa_filename_from_xml,
)
from src.schemas.ricevuta_schema import RicevutaOrderDetailEmbedSchema
from src.schemas.customer_schema import CustomerResponseWithoutAddressSchema
from src.schemas.address_schema import AddressResponseSchema
from src.schemas.payment_schema import PaymentResponseSchema
from src.schemas.shipping_schema import ShippingResponseSchema
from src.core.exceptions import ValidationException, NotFoundException, BusinessRuleException
from src.events.decorators import emit_event_on_success
from src.events.core.event import EventType
from src.events.extractors import (
    extract_invoice_created_data,
    extract_credit_note_created_data
)
from src.services.core.tool import resolve_return_unit_prices
from src.services.ricevute.order_embed_formatters import (
    map_ricevuta_address_embed,
    map_ricevuta_customer_embed,
    map_ricevuta_payment_from_model,
    map_ricevuta_shipping_embed,
)
from src.services.ricevute.order_lines import (
    build_shipping_line_dict,
    load_product_weights,
    resolve_line_product_weight,
    resolve_order_total_weight,
    resolve_shipping_amounts,
)

EXPORT_XLSX_MAX_LIMIT = 5000
EXPORT_XML_MAX_LIMIT = 5000


class FiscalDocumentService(IFiscalDocumentService):
    """Servizio centralizzato per la gestione dei documenti fiscali"""
    
    def __init__(
        self,
        fiscal_document_repository: IFiscalDocumentRepository,
        order_repository: IOrderRepository,
        order_detail_repository: IOrderDetailRepository,
    ):
        self._fiscal_document_repository = fiscal_document_repository
        self._order_repository = order_repository
        self._order_detail_repository = order_detail_repository
        self._export_service = FiscalDocumentExportService()

    @property
    def _session(self):
        return self._fiscal_document_repository._session
    
    @emit_event_on_success(
        event_type=EventType.DOCUMENT_CREATED,
        data_extractor=extract_invoice_created_data,
        source="fiscal_document_service.create_invoice"
    )
    async def create_invoice(self, id_order: int, user: dict = None) -> FiscalDocument:
        """
        Crea una fattura elettronica FatturaPA per un ordine (is_electronic=True).
        """
        try:
            return self._fiscal_document_repository.create_invoice(id_order)
        except Exception as e:
            raise ValidationException(f"Errore nella creazione della fattura: {str(e)}")
    
    @emit_event_on_success(
        event_type=EventType.DOCUMENT_CREATED,
        data_extractor=extract_credit_note_created_data,
        source="fiscal_document_service.create_credit_note"
    )
    async def create_credit_note(self, id_invoice: int, reason: str, is_partial: bool = False, 
                               items: Optional[List[dict]] = None,
                               include_shipping: bool = True, user: dict = None) -> FiscalDocument:
        """Crea una nota di credito elettronica FatturaPA per una fattura (is_electronic=True)."""
        try:
            return self._fiscal_document_repository.create_credit_note(
                id_invoice, reason, is_partial, items, include_shipping
            )
        except ValueError as e:
            raise ValidationException(str(e)) from e
        except Exception as e:
            raise ValidationException(f"Errore nella creazione della nota di credito: {str(e)}")
    
    async def create_return(self, order: Order, return_data: ReturnCreateSchema) -> FiscalDocument:
        """Crea un reso per un ordine"""
        try:
            self._validate_return_payload(order, return_data)

            # Converte i dati dello schema in formato dict
            items_to_return = []
            for item in return_data.order_details:
                order_detail = self._order_detail_repository.get_by_order_detail_id(
                    item.id_order_detail
                )
                ref_net = float(order_detail.unit_price_net or 0) if order_detail else None
                ref_gross = (
                    float(order_detail.unit_price_with_tax or 0) if order_detail else None
                )
                unit_price_net, unit_price_with_tax = resolve_return_unit_prices(
                    unit_price_net=getattr(item, "unit_price_net", None),
                    unit_price_with_tax=getattr(item, "unit_price_with_tax", None),
                    unit_price=item.unit_price,
                    reference_unit_price_net=ref_net,
                    reference_unit_price_with_tax=ref_gross,
                )
                items_to_return.append({
                    'id_order_detail': item.id_order_detail,
                    'quantity': item.quantity,
                    'unit_price_net': unit_price_net,
                    'unit_price_with_tax': unit_price_with_tax,
                    'id_tax': item.id_tax or (order_detail.id_tax if order_detail else None),
                })

            if items_to_return:
                items_already_returned = await self.get_items_returned_by_order(order.id_order)
                items_already_returned_dict = {}
                if items_already_returned:
                    for item in items_already_returned:
                        id_order_detail = item['id_order_detail']
                        if id_order_detail not in items_already_returned_dict:
                            items_already_returned_dict[id_order_detail] = {
                                k: v for k, v in item.items() if k != 'id_order_detail'
                            }
                        else:
                            items_already_returned_dict[id_order_detail]['quantity_returned'] += item[
                                'quantity_returned'
                            ]
                is_returnable = await self.validate_return_items(
                    items_to_return, items_already_returned_dict
                )
                if not is_returnable:
                    raise ValidationException(
                        "Non è possibile creare il reso per questi articoli. "
                        "Controllare la quantità di articoli già resi e la quantità da restituire."
                    )
            return self._fiscal_document_repository.create_return(
                order,
                items_to_return,
                return_data.includes_shipping,
                return_data.note,
            )
        except ValidationException:
            raise
        except Exception as e:
            raise ValidationException(f"Errore nella creazione del reso: {str(e)}")
    
    async def update_fiscal_document(self, id_fiscal_document: int, update_data: ReturnUpdateSchema) -> FiscalDocument:
        """Aggiorna un documento fiscale"""
        try:
            # Recupera il documento esistente
            fiscal_doc = self._fiscal_document_repository.get_by_id(id_fiscal_document)
            if not fiscal_doc:
                raise NotFoundException(f"Documento fiscale {id_fiscal_document} non trovato")
            
            # Aggiorna i campi se forniti
            if update_data.includes_shipping is not None:
                fiscal_doc.includes_shipping = update_data.includes_shipping
            
            if update_data.note is not None:
                fiscal_doc.credit_note_reason = update_data.note
            
            if update_data.status is not None:
                if update_data.status not in ['pending', 'processed', 'cancelled']:
                    raise ValidationException("Status non valido. Valori ammessi: pending, processed, cancelled")
                fiscal_doc.status = update_data.status
            
            # Ricalcola il totale se necessario
            if update_data.includes_shipping is not None:
                self._fiscal_document_repository.recalculate_fiscal_document_total(id_fiscal_document)
            
            return self._fiscal_document_repository.update(fiscal_doc)
        except Exception as e:
            raise ValidationException(f"Errore nell'aggiornamento del documento fiscale: {str(e)}")
    
    async def delete_fiscal_document(self, id_fiscal_document: int) -> bool:
        """Elimina un documento fiscale (resi in qualsiasi stato; altri tipi solo pending)."""
        fiscal_doc = self._fiscal_document_repository.get_by_id(id_fiscal_document)
        if not fiscal_doc:
            raise NotFoundException("FiscalDocument", id_fiscal_document)

        if fiscal_doc.status != "pending" and fiscal_doc.document_type != "return":
            raise BusinessRuleException(
                "Solo i documenti in stato 'pending' possono essere eliminati "
                "(i resi sono eliminabili in qualsiasi stato)"
            )

        try:
            deleted = self._fiscal_document_repository.delete_fiscal_document(
                id_fiscal_document
            )
        except ValueError as exc:
            raise BusinessRuleException(str(exc)) from exc

        if not deleted:
            raise NotFoundException("FiscalDocument", id_fiscal_document)
        return True
    
    async def update_fiscal_document_detail(self, id_detail: int, update_data: ReturnDetailUpdateSchema) -> FiscalDocumentDetail:
        """Aggiorna un dettaglio di documento fiscale"""
        try:
            return self._fiscal_document_repository.update_fiscal_document_detail(
                id_detail,
                update_data.quantity,
                update_data.unit_price,
                update_data.id_tax
            )
        except Exception as e:
            raise ValidationException(f"Errore nell'aggiornamento del dettaglio: {str(e)}")
    
    async def delete_fiscal_document_detail(self, id_detail: int) -> bool:
        """Elimina un dettaglio di reso e ricalcola il totale del documento."""
        try:
            deleted = self._fiscal_document_repository.delete_fiscal_document_detail(
                id_detail
            )
        except ValueError as exc:
            raise BusinessRuleException(str(exc)) from exc

        if not deleted:
            raise NotFoundException("FiscalDocumentDetail", id_detail)
        return True

    def _row_to_return_response_schema(self, row) -> Optional[ReturnResponseSchema]:
        """Converte una tupla (doc, addr_del, addr_inv, customer, payment, shipping) in ReturnResponseSchema.
        I dettagli (details) hanno la stessa struttura del dettaglio order_detail (OrderDetailResponseSchema).
        """
        if not row:
            return None
        doc, address_delivery, address_invoice, customer, payment, shipping = row

        def _float(v):
            return float(v) if v is not None else None

        customer_schema = CustomerResponseWithoutAddressSchema.from_orm(customer) if customer else None
        addr_del_schema = AddressResponseSchema.from_orm(address_delivery) if address_delivery else None
        addr_inv_schema = AddressResponseSchema.from_orm(address_invoice) if address_invoice else None
        payment_schema = PaymentResponseSchema.from_orm(payment) if payment else None
        shipping_schema = ShippingResponseSchema.from_orm(shipping) if shipping else None

        details_list = doc.details or []
        order_detail_map = self._fiscal_document_repository.get_order_details_with_images(
            [d.id_order_detail for d in details_list]
        ) if details_list else {}

        details_schemas = []
        for d in details_list:
            od_data = order_detail_map.get(d.id_order_detail, {})
            od = od_data.get("order_detail")
            img_url = od_data.get("img_url")
            if od:
                details_schemas.append(
                    ReturnDetailResponseSchema(
                        id_order_detail=od.id_order_detail,
                        id_order=od.id_order,
                        id_order_document=od.id_order_document,
                        id_origin=od.id_origin,
                        id_tax=d.id_tax or od.id_tax,
                        id_product=od.id_product,
                        product_name=od.product_name,
                        product_reference=od.product_reference or None,
                        product_qty=d.product_qty,
                        unit_price_net=_float(d.unit_price_net),
                        unit_price_with_tax=_float(d.unit_price_with_tax) if d.unit_price_with_tax is not None else 0.0,
                        total_price_net=_float(d.total_price_net) if d.total_price_net is not None else 0.0,
                        total_price_with_tax=_float(d.total_price_with_tax) if d.total_price_with_tax is not None else 0.0,
                        product_weight=_float(od.product_weight) if od.product_weight is not None else None,
                        reduction_percent=_float(od.reduction_percent) if getattr(od, "reduction_percent", None) is not None else None,
                        reduction_amount=_float(od.reduction_amount) if getattr(od, "reduction_amount", None) is not None else None,
                        rda=getattr(d, "rda", None) or getattr(od, "rda", None),
                        rda_quantity=getattr(od, "rda_quantity", None),
                        note=getattr(od, "note", None),
                        img_url=img_url,
                        id_fiscal_document_detail=d.id_fiscal_document_detail,
                        id_fiscal_document=d.id_fiscal_document,
                        is_shipping=False,
                    )
                )
            else:
                details_schemas.append(
                    ReturnDetailResponseSchema(
                        id_order_detail=d.id_order_detail,
                        id_order=doc.id_order,
                        id_order_document=None,
                        id_origin=None,
                        id_tax=d.id_tax,
                        id_product=None,
                        product_name=None,
                        product_reference=None,
                        product_qty=d.product_qty,
                        unit_price_net=_float(d.unit_price_net),
                        unit_price_with_tax=_float(d.unit_price_with_tax) if d.unit_price_with_tax is not None else 0.0,
                        total_price_net=_float(d.total_price_net) if d.total_price_net is not None else 0.0,
                        total_price_with_tax=_float(d.total_price_with_tax) if d.total_price_with_tax is not None else 0.0,
                        product_weight=None,
                        reduction_percent=None,
                        reduction_amount=None,
                        rda=getattr(d, "rda", None),
                        rda_quantity=None,
                        note=None,
                        img_url=None,
                        id_fiscal_document_detail=d.id_fiscal_document_detail,
                        id_fiscal_document=d.id_fiscal_document,
                        is_shipping=False,
                    )
                )

        if doc.includes_shipping:
            order = self._order_repository.get_by_id(doc.id_order)
            shipping_line = self._build_return_shipping_detail(doc, order, shipping)
            if shipping_line:
                details_schemas.append(shipping_line)

        return ReturnResponseSchema(
            id_fiscal_document=doc.id_fiscal_document,
            id_order=doc.id_order,
            document_number=doc.document_number,
            date_add=doc.date_add,
            filename=doc.filename,
            xml_content=doc.xml_content,
            status=doc.status,
            upload_result=doc.upload_result,
            date_upd=doc.date_upd,
            document_type=doc.document_type,
            tipo_documento_fe=doc.tipo_documento_fe,
            id_fiscal_document_ref=doc.id_fiscal_document_ref,
            internal_number=doc.internal_number,
            credit_note_reason=doc.credit_note_reason,
            is_partial=doc.is_partial,
            total_price_with_tax=_float(doc.total_price_with_tax),
            includes_shipping=doc.includes_shipping,
            customer=customer_schema,
            address_delivery=addr_del_schema,
            address_invoice=addr_inv_schema,
            payment=payment_schema,
            shipping=shipping_schema,
            details=details_schemas,
        )

    @staticmethod
    def _to_float(v):
        return round(float(v), 2) if v is not None else None

    def _resolve_invoice_shipping_totals(self, doc, order, shipping):
        if not doc.includes_shipping:
            return None, None
        prod_net = float(doc.products_total_price_net or 0)
        prod_incl = float(doc.products_total_price_with_tax or 0)
        total_net = float(doc.total_price_net or 0)
        total_incl = float(doc.total_price_with_tax or 0)
        ship_net = round(total_net - prod_net, 2) if total_net > prod_net else None
        ship_incl = round(total_incl - prod_incl, 2) if total_incl > prod_incl else None
        if (ship_net is None or ship_net <= 0) and order and shipping:
            ship_net, ship_incl = resolve_shipping_amounts(order, shipping)
            ship_net = ship_net if ship_net > 0 else None
            ship_incl = ship_incl if ship_incl > 0 else None
        return ship_net, ship_incl

    def _build_invoice_order_details(self, doc, order, shipping, order_detail_map, product_weights):
        order_details: list[RicevutaOrderDetailEmbedSchema] = []
        for detail in doc.details or []:
            od_data = order_detail_map.get(detail.id_order_detail, {})
            od = od_data.get("order_detail")
            line_weight = resolve_line_product_weight(od, product_weights) if od else None
            order_details.append(
                RicevutaOrderDetailEmbedSchema(
                    id_order_detail=detail.id_order_detail,
                    id_product=od.id_product if od else None,
                    product_name=od.product_name if od else None,
                    product_reference=od.product_reference if od else None,
                    product_qty=int(detail.product_qty or 0),
                    product_weight=self._to_float(line_weight),
                    id_tax=detail.id_tax or (od.id_tax if od else None),
                    unit_price_net=self._to_float(detail.unit_price_net),
                    unit_price_with_tax=self._to_float(detail.unit_price_with_tax),
                    total_price_net=self._to_float(detail.total_price_net),
                    total_price_with_tax=self._to_float(detail.total_price_with_tax),
                    reduction_percent=self._to_float(getattr(od, "reduction_percent", None))
                    if od
                    else None,
                    reduction_amount=self._to_float(getattr(od, "reduction_amount", None))
                    if od
                    else None,
                    is_shipping=False,
                )
            )

        if doc.includes_shipping and order:
            shipping_line = build_shipping_line_dict(order, shipping)
            if shipping_line:
                order_details.append(RicevutaOrderDetailEmbedSchema(**shipping_line))
        return order_details

    def _row_to_fiscal_document_detail_schema(self, row) -> Optional[InvoiceResponseSchema]:
        """Converte (doc, addr_del, addr_inv, customer, payment, shipping) in schema v3."""
        if not row:
            return None
        doc, address_delivery, address_invoice, customer, payment, shipping = row
        if doc.document_type not in ("invoice", "credit_note"):
            return None

        order = self._order_repository.get_by_id(doc.id_order)
        details_list = doc.details or []
        order_detail_map = (
            self._fiscal_document_repository.get_order_details_with_images(
                [d.id_order_detail for d in details_list if d.id_order_detail]
            )
            if details_list
            else {}
        )
        product_ids = [
            data.get("order_detail").id_product
            for data in order_detail_map.values()
            if data.get("order_detail") and data["order_detail"].id_product
        ]
        product_weights = load_product_weights(self._session, product_ids)
        raw_order_details = (
            self._order_detail_repository.get_by_order_id(doc.id_order)
            if order
            else []
        )
        ship_net, ship_incl = self._resolve_invoice_shipping_totals(doc, order, shipping)
        is_credit_note = doc.document_type == "credit_note"

        return InvoiceResponseSchema(
            id_fiscal_document=doc.id_fiscal_document,
            document_type=doc.document_type,
            tipo_documento_fe=doc.tipo_documento_fe,
            id_order=doc.id_order,
            id_fiscal_document_ref=doc.id_fiscal_document_ref if is_credit_note else None,
            document_number=doc.document_number,
            internal_number=doc.internal_number,
            filename=doc.filename,
            xml_content=doc.xml_content,
            status=doc.status,
            is_electronic=bool(doc.is_electronic),
            upload_result=doc.upload_result,
            credit_note_reason=doc.credit_note_reason if is_credit_note else None,
            is_partial=bool(doc.is_partial) if is_credit_note else None,
            includes_shipping=bool(doc.includes_shipping),
            total_price_with_tax=self._to_float(doc.total_price_with_tax),
            total_price_net=self._to_float(doc.total_price_net),
            products_total_price_net=self._to_float(doc.products_total_price_net),
            products_total_price_with_tax=self._to_float(doc.products_total_price_with_tax),
            date_add=doc.date_add,
            date_upd=doc.date_upd,
            order_reference=order.reference if order else None,
            id_order_state=order.id_order_state if order else None,
            total_weight=resolve_order_total_weight(
                order, raw_order_details, shipping, product_weights
            )
            if order
            else None,
            vies_status=order.vies_status if order else None,
            is_payed=bool(order.is_payed) if order else False,
            payment_due_date=order.payment_due_date if order else None,
            payment=map_ricevuta_payment_from_model(payment),
            shipping=map_ricevuta_shipping_embed(self._session, shipping),
            shipping_total_price_with_tax=ship_incl,
            shipping_total_price_net=ship_net,
            total_discounts=self._to_float(order.total_discounts) if order else None,
            customer=map_ricevuta_customer_embed(customer),
            address_delivery=map_ricevuta_address_embed(address_delivery),
            address_invoice=map_ricevuta_address_embed(address_invoice),
            order_details=self._build_invoice_order_details(
                doc, order, shipping, order_detail_map, product_weights
            ),
        )

    def _row_to_invoice_response_schema(self, row) -> Optional[InvoiceResponseSchema]:
        schema = self._row_to_fiscal_document_detail_schema(row)
        if schema and schema.document_type != "invoice":
            return None
        return schema

    async def get_invoices_by_order_response(self, id_order: int) -> List[InvoiceResponseSchema]:
        """Fatture ordine arricchite (contratto allineato a ricevuta v3)."""
        try:
            rows = self._fiscal_document_repository.get_by_order_id(
                id_order, page=1, limit=100, document_type="invoice"
            )
            schemas = [self._row_to_invoice_response_schema(r) for r in rows]
            return [s for s in schemas if s is not None]
        except Exception as e:
            raise ValidationException(f"Errore nel recupero delle fatture: {str(e)}")

    async def get_invoice_response_by_id(self, id_fiscal_document: int) -> InvoiceResponseSchema:
        """Dettaglio fattura per ID con relazioni ordine."""
        schema = await self.get_fiscal_document_detail_response_by_id(id_fiscal_document)
        if schema.document_type != "invoice":
            raise NotFoundException(f"Fattura {id_fiscal_document} non trovata")
        return schema

    async def get_fiscal_document_detail_response_by_id(
        self, id_fiscal_document: int
    ) -> InvoiceResponseSchema:
        """Dettaglio fattura o nota di credito (contratto v3 arricchito)."""
        row = self._fiscal_document_repository.get_fiscal_document_with_relations_by_id(
            id_fiscal_document
        )
        if not row:
            raise NotFoundException(f"Documento fiscale {id_fiscal_document} non trovato")
        schema = self._row_to_fiscal_document_detail_schema(row)
        if not schema:
            raise NotFoundException(f"Documento fiscale {id_fiscal_document} non trovato")
        return schema

    async def get_credit_notes_by_invoice_response(
        self, id_invoice: int
    ) -> List[InvoiceResponseSchema]:
        """Note di credito di una fattura (contratto v3 arricchito)."""
        try:
            credit_notes = self._fiscal_document_repository.get_credit_notes_by_invoice(
                id_invoice
            )
            results: List[InvoiceResponseSchema] = []
            for cn in credit_notes:
                row = self._fiscal_document_repository.get_fiscal_document_with_relations_by_id(
                    cn.id_fiscal_document
                )
                schema = self._row_to_fiscal_document_detail_schema(row)
                if schema:
                    results.append(schema)
            return results
        except Exception as e:
            raise ValidationException(
                f"Errore nel recupero delle note di credito: {str(e)}"
            ) from e

    async def get_fiscal_documents_by_order(self, id_order: int, page: int = 1, limit: int = 10, document_type: Optional[str] = None) -> List[ReturnResponseSchema]:
        """Ottiene i documenti fiscali per un ordine, formattati come ReturnResponseSchema."""
        try:
            result = self._fiscal_document_repository.get_by_order_id(id_order, page, limit, document_type)
            schemas = [self._row_to_return_response_schema(r) for r in result]
            return [s for s in schemas if s is not None]
        except Exception as e:
            raise ValidationException(f"Errore nel recupero dei documenti fiscali: {str(e)}")
    
    async def get_fiscal_documents_by_type(self, document_type: str, page: int = 1, limit: int = 10) -> List[FiscalDocument]:
        """Ottiene i documenti fiscali per tipo"""
        try:
            return self._fiscal_document_repository.get_by_document_type(document_type, page, limit)
        except Exception as e:
            raise ValidationException(f"Errore nel recupero dei documenti fiscali per tipo: {str(e)}")
    
    async def get_fiscal_document_count_by_type(self, document_type: str) -> int:
        """Conta i documenti fiscali per tipo"""
        try:
            return self._fiscal_document_repository.get_document_count_by_type(document_type)
        except Exception as e:
            raise ValidationException(f"Errore nel conteggio dei documenti fiscali: {str(e)}")
    
    # Metodi di utilità per la numerazione sequenziale
    async def get_next_document_number(self, document_type: str) -> int:
        """Ottiene il prossimo numero sequenziale per un tipo di documento"""
        try:
            return self._fiscal_document_repository.get_next_document_number(document_type)
        except Exception as e:
            raise ValidationException(f"Errore nella generazione del numero sequenziale: {str(e)}")
    
    
    async def get_items_returned_by_order(self, id_order: int):
        """Recupera gli articoli già resi per un ordine (richiama get_items_returned_by_order del repository)"""
        try:
            return self._fiscal_document_repository.get_items_returned_by_order(id_order)
        except Exception as e:
            raise ValidationException(f"Errore nel recupero degli articoli resi: {str(e)}")
    
    # ==================== METODI CENTRALIZZATI PER FATTURE E NOTE DI CREDITO ====================
    
    async def get_next_electronic_number(self, doc_type: str) -> str:
        """Ottiene il prossimo numero sequenziale elettronico per un tipo di documento"""
        try:
            return self._fiscal_document_repository._get_next_electronic_number(doc_type)
        except Exception as e:
            raise ValidationException(f"Errore nella generazione del numero elettronico: {str(e)}")
    
    async def get_invoice_by_order(self, id_order: int):
        """Recupera la prima fattura di un ordine (deprecato, usare get_invoices_by_order)"""
        try:
            return self._fiscal_document_repository.get_invoice_by_order(id_order)
        except Exception as e:
            raise ValidationException(f"Errore nel recupero della fattura: {str(e)}")
    
    async def get_invoices_by_order(self, id_order: int):
        """Recupera tutte le fatture di un ordine"""
        try:
            return self._fiscal_document_repository.get_invoices_by_order(id_order)
        except Exception as e:
            raise ValidationException(f"Errore nel recupero delle fatture: {str(e)}")
    
    async def get_credit_notes_by_invoice(self, id_invoice: int):
        """Recupera tutte le note di credito di una fattura"""
        try:
            return self._fiscal_document_repository.get_credit_notes_by_invoice(id_invoice)
        except Exception as e:
            raise ValidationException(f"Errore nel recupero delle note di credito: {str(e)}")

    async def get_credit_note_eligible_lines(
        self, id_fiscal_document: int
    ) -> CreditNoteEligibleLinesResponseSchema:
        """Righe fattura per modale NC parziale."""
        try:
            payload = self._fiscal_document_repository.get_credit_note_eligible_lines(
                id_fiscal_document
            )
            return CreditNoteEligibleLinesResponseSchema(**payload)
        except ValueError as e:
            raise NotFoundException(str(e)) from e
        except Exception as e:
            raise ValidationException(
                f"Errore nel recupero righe eleggibili per NC: {str(e)}"
            ) from e
    
    async def get_fiscal_document_by_id(self, id_fiscal_document: int) -> ReturnResponseSchema:
        """Recupera documento fiscale per ID con relazioni, formattato come ReturnResponseSchema."""
        row = self._fiscal_document_repository.get_fiscal_document_with_relations_by_id(id_fiscal_document)
        if not row:
            raise NotFoundException(f"Documento fiscale {id_fiscal_document} non trovato")
        schema = self._row_to_return_response_schema(row)
        if not schema:
            raise NotFoundException(f"Documento fiscale {id_fiscal_document} non trovato")
        return schema
    
    async def get_fiscal_documents(
        self,
        skip: int = 0,
        limit: int = 100,
        document_type: Optional[str] = None,
        is_electronic: Optional[bool] = None,
        status: Optional[str] = None,
        delivery_country_iso: Optional[str] = None,
        date_add_from: Optional[date] = None,
        date_add_to: Optional[date] = None,
    ):
        """Recupera lista documenti fiscali con filtri"""
        try:
            date_from, date_to = self._export_date_bounds(date_add_from, date_add_to)
            return self._fiscal_document_repository.get_fiscal_documents(
                skip,
                limit,
                document_type,
                is_electronic,
                status,
                delivery_country_iso,
                date_from,
                date_to,
            )
        except Exception as e:
            raise ValidationException(f"Errore nel recupero dei documenti fiscali: {str(e)}")
    
    async def update_fiscal_document_status(self, id_fiscal_document: int, status: str, upload_result: Optional[str] = None):
        """Aggiorna status di un documento fiscale"""
        try:
            return self._fiscal_document_repository.update_fiscal_document_status(id_fiscal_document, status, upload_result)
        except Exception as e:
            raise ValidationException(f"Errore nell'aggiornamento dello status: {str(e)}")
    
    async def update_fiscal_document_xml(self, id_fiscal_document: int, filename: str, xml_content: str):
        """Aggiorna XML di un documento fiscale"""
        try:
            return self._fiscal_document_repository.update_fiscal_document_xml(id_fiscal_document, filename, xml_content)
        except Exception as e:
            raise ValidationException(f"Errore nell'aggiornamento dell'XML: {str(e)}")
    
    async def delete_fiscal_document_legacy(self, id_fiscal_document: int) -> bool:
        """Elimina documento fiscale (versione legacy per compatibilità)"""
        try:
            return self._fiscal_document_repository.delete_fiscal_document(id_fiscal_document)
        except Exception as e:
            raise ValidationException(f"Errore nell'eliminazione del documento fiscale: {str(e)}")
    
    async def validate_business_rules(self, entity_data: dict) -> None:
        """Valida le regole di business per i documenti fiscali"""
        # Implementazione delle regole di business specifiche per i documenti fiscali
        # Per ora, implementazione vuota - può essere estesa in futuro
        pass
    
    async def validate_return_items(self, items_to_return: List[dict], items_already_returned: List[dict]) -> bool:
        """Valida il reso in base agli articoli da restituire e agli articoli già resi"""
        if not items_to_return:
            return False
        if not items_already_returned:
            return True

        for item in items_to_return:
            id_order_detail = item['id_order_detail']
            order_detail = self._order_detail_repository.get_by_order_detail_id(id_order_detail)
            if not order_detail:
                return False
            total_quantity_bought = order_detail.product_qty
            quantity_to_return = item['quantity']
            quantity_already_returned = items_already_returned.get(id_order_detail, {}).get('quantity_returned', 0)
            total_quantity = quantity_to_return + quantity_already_returned

            if total_quantity > total_quantity_bought:
                return False
        return True

    def _validate_return_payload(self, order: Order, return_data: ReturnCreateSchema) -> None:
        has_products = bool(return_data.order_details)
        if not has_products and not return_data.includes_shipping:
            raise ValidationException(
                "Specificare almeno una riga prodotto o impostare includes_shipping=true"
            )

        if return_data.includes_shipping:
            if self._fiscal_document_repository.is_shipping_already_returned(order.id_order):
                raise ValidationException(
                    "Le spese di spedizione sono già state incluse in un reso precedente"
                )
            shipping_net, shipping_incl = resolve_shipping_amounts(
                order,
                self._fiscal_document_repository.get_order_shipping(order),
            )
            if shipping_net <= 0 and shipping_incl <= 0:
                raise ValidationException(
                    "L'ordine non ha costi di spedizione da restituire"
                )

    def _build_return_shipping_detail(
        self,
        doc: FiscalDocument,
        order: Optional[Order],
        shipping,
    ) -> Optional[ReturnDetailResponseSchema]:
        if not order:
            return None
        shipping_line = build_shipping_line_dict(order, shipping, product_reference="SHIPPING")
        if not shipping_line:
            return None
        return ReturnDetailResponseSchema(
            id_order_detail=0,
            id_order=doc.id_order,
            id_tax=shipping_line.get("id_tax"),
            product_name=shipping_line.get("product_name"),
            product_reference=shipping_line.get("product_reference"),
            product_qty=int(shipping_line.get("product_qty") or 1),
            unit_price_net=self._to_float(shipping_line.get("unit_price_net")),
            unit_price_with_tax=self._to_float(shipping_line.get("unit_price_with_tax")) or 0.0,
            total_price_net=self._to_float(shipping_line.get("total_price_net")) or 0.0,
            total_price_with_tax=self._to_float(shipping_line.get("total_price_with_tax")) or 0.0,
            id_fiscal_document=doc.id_fiscal_document,
            is_shipping=True,
        )

    @staticmethod
    def _export_date_bounds(
        date_add_from: Optional[date],
        date_add_to: Optional[date],
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        start = datetime.combine(date_add_from, time.min) if date_add_from else None
        end = datetime.combine(date_add_to, time.max) if date_add_to else None
        return start, end

    def _map_invoice_export_row(self, row) -> InvoiceListExportItemSchema:
        fiscal_document, order, customer, address_delivery, country_delivery = row
        return InvoiceListExportItemSchema(
            id_fiscal_document=fiscal_document.id_fiscal_document,
            document_type=fiscal_document.document_type,
            document_number=fiscal_document.document_number,
            internal_number=fiscal_document.internal_number,
            tipo_documento_fe=fiscal_document.tipo_documento_fe,
            status=fiscal_document.status,
            is_electronic=fiscal_document.is_electronic,
            id_order=fiscal_document.id_order,
            order_reference=order.reference if order else None,
            customer_firstname=customer.firstname if customer else None,
            customer_lastname=customer.lastname if customer else None,
            customer_email=customer.email if customer else None,
            delivery_country_iso=country_delivery.iso_code if country_delivery else None,
            delivery_city=address_delivery.city if address_delivery else None,
            date_add=fiscal_document.date_add,
            total_price_net=fiscal_document.total_price_net,
            total_price_with_tax=fiscal_document.total_price_with_tax,
            products_total_price_net=fiscal_document.products_total_price_net,
            products_total_price_with_tax=fiscal_document.products_total_price_with_tax,
        )

    def _list_invoices_for_export(
        self,
        filters: InvoiceExportFiltersSchema,
    ) -> tuple[List[InvoiceListExportItemSchema], int]:
        date_from, date_to = self._export_date_bounds(
            filters.date_add_from, filters.date_add_to
        )
        total = self._fiscal_document_repository.count_invoices_for_export(
            document_type=filters.document_type,
            is_electronic=filters.is_electronic,
            status=filters.status,
            id_order=filters.id_order,
            id_customer=filters.id_customer,
            delivery_country_iso=filters.delivery_country_iso,
            date_add_from=date_from,
            date_add_to=date_to,
        )
        skip = (filters.page - 1) * filters.limit
        rows = self._fiscal_document_repository.list_invoices_for_export(
            skip=skip,
            limit=filters.limit,
            document_type=filters.document_type,
            is_electronic=filters.is_electronic,
            status=filters.status,
            id_order=filters.id_order,
            id_customer=filters.id_customer,
            delivery_country_iso=filters.delivery_country_iso,
            date_add_from=date_from,
            date_add_to=date_to,
        )
        return [self._map_invoice_export_row(row) for row in rows], total

    @staticmethod
    def _parse_export_format(fmt: str) -> InvoiceExportFormatSchema:
        normalized = (fmt or "").strip().lower()
        try:
            return InvoiceExportFormatSchema(normalized)
        except ValueError as exc:
            raise ValidationException(
                "Formato export non valido: usare xlsx o xml (il PDF è solo singolo: GET /{id}/pdf)",
                details={"fmt": fmt, "allowed": ["xlsx", "xml"]},
            ) from exc

    @staticmethod
    def _export_filename_suffix(filters: InvoiceExportFiltersSchema) -> str:
        suffix = ""
        if filters.delivery_country_iso:
            suffix += f"-{filters.delivery_country_iso}"
        if filters.date_add_from and filters.date_add_to:
            suffix += (
                f"-{filters.date_add_from.isoformat()}"
                f"-{filters.date_add_to.isoformat()}"
            )
        elif filters.date_add_from:
            suffix += f"-from-{filters.date_add_from.isoformat()}"
        elif filters.date_add_to:
            suffix += f"-to-{filters.date_add_to.isoformat()}"
        return suffix

    def _export_max_limit(self, export_fmt: InvoiceExportFormatSchema) -> int:
        if export_fmt == InvoiceExportFormatSchema.XML:
            return EXPORT_XML_MAX_LIMIT
        return EXPORT_XLSX_MAX_LIMIT

    @staticmethod
    def _export_label_prefix(document_type: str) -> str:
        return "note-credito" if document_type == "credit_note" else "fatture"

    @staticmethod
    def _export_sheet_title(document_type: str) -> str:
        return (
            "Note di credito" if document_type == "credit_note" else "Fatture"
        )

    def _ensure_fiscal_document_xml(self, id_fiscal_document: int) -> None:
        """Genera e persiste XML FatturaPA se mancante."""
        from src.services.external.fatturapa_service import FatturaPAService

        doc = self._fiscal_document_repository.get_fiscal_document_by_id(
            id_fiscal_document
        )
        if not doc:
            raise NotFoundException("FiscalDocument", id_fiscal_document)
        if doc.xml_content:
            return

        result = FatturaPAService(self._session).generate_xml_from_fiscal_document(
            id_fiscal_document
        )
        if result.get("status") == "validation_error":
            raise ValidationException(
                f"Validazione XML FatturaPA fallita per documento {id_fiscal_document}",
                details={
                    "id_fiscal_document": id_fiscal_document,
                    "errors": result.get("errors", []),
                },
            )
        if result.get("status") != "success":
            raise ValidationException(
                result.get(
                    "message",
                    f"Generazione XML fallita per documento {id_fiscal_document}",
                ),
                details={"id_fiscal_document": id_fiscal_document, "result": result},
            )

        self._fiscal_document_repository.update_fiscal_document_xml(
            id_fiscal_document,
            result["filename"],
            result["xml_content"],
        )

    def _ensure_invoice_xml(self, invoice_id: int) -> None:
        """Backward-compatible wrapper."""
        self._ensure_fiscal_document_xml(invoice_id)

    def _prepare_fiscal_document_ids_for_xml_export(
        self, document_ids: List[int]
    ) -> tuple[List[int], List[Dict[str, Any]]]:
        ready: List[int] = []
        failures: List[Dict[str, Any]] = []
        for document_id in document_ids:
            try:
                self._ensure_fiscal_document_xml(document_id)
                ready.append(document_id)
            except (ValidationException, NotFoundException) as exc:
                failures.append(
                    {
                        "id_fiscal_document": document_id,
                        "message": exc.message,
                        "details": exc.details,
                    }
                )
        return ready, failures

    def _prepare_invoice_ids_for_xml_export(
        self, invoice_ids: List[int]
    ) -> tuple[List[int], List[Dict[str, Any]]]:
        return self._prepare_fiscal_document_ids_for_xml_export(invoice_ids)

    def _load_fiscal_document_xml(self, id_fiscal_document: int) -> tuple[bytes, str]:
        doc = self._fiscal_document_repository.get_fiscal_document_by_id(
            id_fiscal_document
        )
        if not doc:
            raise NotFoundException(f"Documento {id_fiscal_document} non trovato")
        if not doc.xml_content:
            raise ValidationException(
                f"Documento {id_fiscal_document} senza XML generato",
                details={"id_fiscal_document": id_fiscal_document},
            )
        fallback = (
            f"nota-credito-{id_fiscal_document}.xml"
            if doc.document_type == "credit_note"
            else f"fattura-{id_fiscal_document}.xml"
        )
        filename = resolve_fatturapa_filename_from_xml(
            doc.xml_content,
            fallback_filename=doc.filename or fallback,
        )
        return normalize_xml_bytes(doc.xml_content), filename

    def _load_invoice_xml(self, invoice_id: int) -> tuple[bytes, str]:
        return self._load_fiscal_document_xml(invoice_id)

    @staticmethod
    def _summarize_xml_export_failures(
        failures: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Raggruppa errori export XML per messaggio (es. P.IVA invalida)."""
        buckets: Dict[str, Dict[str, Any]] = {}
        for item in failures:
            message = item.get("message") or "Errore sconosciuto"
            key = message
            if key not in buckets:
                buckets[key] = {
                    "message": message,
                    "count": 0,
                    "id_fiscal_documents": [],
                }
            buckets[key]["count"] += 1
            buckets[key]["id_fiscal_documents"].append(item.get("id_fiscal_document"))
        return list(buckets.values())

    async def export_invoices(
        self, filters: InvoiceExportFiltersSchema, fmt: str
    ) -> Tuple[bytes, str, str]:
        """Export massivo fatture o note di credito in Excel o ZIP XML."""
        export_fmt = self._parse_export_format(fmt)
        max_limit = self._export_max_limit(export_fmt)
        label_prefix = self._export_label_prefix(filters.document_type)

        if export_fmt == InvoiceExportFormatSchema.XML:
            export_filters = filters.for_xml_export(max_limit=max_limit)
        else:
            export_filters = filters.model_copy(update={"page": 1, "limit": max_limit})

        items, total = self._list_invoices_for_export(export_filters)

        if total == 0:
            raise NotFoundException(
                "InvoiceExport",
                None,
                details={
                    "message": (
                        "Nessun documento trovato con i filtri indicati "
                        f"(document_type={export_filters.document_type})"
                    ),
                    "fmt": export_fmt.value,
                    "filters": export_filters.model_dump(mode="json"),
                },
            )

        if total > max_limit:
            raise ValidationException(
                f"Troppi record per export ({total}); restringere i filtri "
                f"(max {max_limit})",
                details={"total": total, "max": max_limit},
            )

        suffix = self._export_filename_suffix(
            export_filters if export_fmt == InvoiceExportFormatSchema.XML else filters
        )

        if export_fmt == InvoiceExportFormatSchema.XLSX:
            content = self._export_service.build_list_xlsx(
                items,
                sheet_title=self._export_sheet_title(export_filters.document_type),
            )
            media_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            filename = f"{label_prefix}-export{suffix}.xlsx"
            return content, media_type, filename

        document_ids = [item.id_fiscal_document for item in items]
        ready_ids, xml_failures = self._prepare_fiscal_document_ids_for_xml_export(
            document_ids
        )
        if not ready_ids:
            summary = self._summarize_xml_export_failures(xml_failures)
            raise ValidationException(
                "Nessun documento esportabile in XML FatturaPA",
                details={
                    "fmt": "xml",
                    "document_type": export_filters.document_type,
                    "failed": xml_failures,
                    "failure_summary": summary,
                    "total_candidates": len(document_ids),
                    "hint": (
                        "Verificare P.IVA/CF e indirizzi fatturazione; "
                        "restringere con date_add_from/to e delivery_country_iso"
                    ),
                },
            )

        zip_prefix = (
            "nota-credito"
            if export_filters.document_type == "credit_note"
            else "fattura"
        )
        content = self._export_service.build_xml_zip(
            ready_ids,
            self._load_fiscal_document_xml,
            duplicate_prefix=zip_prefix,
        )
        media_type = "application/zip"
        filename = f"{label_prefix}-xml-export{suffix}.zip"
        return content, media_type, filename
    