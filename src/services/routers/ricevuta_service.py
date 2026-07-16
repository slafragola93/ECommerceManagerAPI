"""Service ricevute — lettura con join live ordine/cliente/order_details."""

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy.orm import joinedload

from src.core.exceptions import (
    BusinessRuleException,
    ErrorCode,
    NotFoundException,
    ValidationException,
)
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.ricevuta import ORDER_STATE_SPEDIZIONE_CONFERMATA, Ricevuta, RicevutaStato
from src.repository.interfaces.address_repository_interface import IAddressRepository
from src.repository.interfaces.customer_repository_interface import ICustomerRepository
from src.repository.interfaces.order_detail_repository_interface import IOrderDetailRepository
from src.repository.interfaces.order_repository_interface import IOrderRepository
from src.repository.interfaces.ricevuta_repository_interface import IRicevutaRepository
from src.schemas.ricevuta_schema import (
    RicevutaAddressEmbedSchema,
    RicevutaCountryEmbedSchema,
    RicevutaCreateSchema,
    RicevutaCustomerEmbedSchema,
    RicevutaExportFormatSchema,
    RicevutaFiltersSchema,
    RicevutaListItemSchema,
    RicevutaListResponseSchema,
    RicevutaResponseSchema,
    RicevutaOrderDetailEmbedSchema,
    RicevutaStatoSchema,
    RicevutaUpdateSchema,
)
from src.services.ricevute.order_embed_formatters import (
    map_ricevuta_payment_embed,
    map_ricevuta_shipping_embed,
)
from src.services.export.ricevuta_export_service import RicevutaExportService
from src.services.interfaces.ricevuta_service_interface import IRicevutaService
from src.services.pdf.ricevuta_pdf_service import RicevutaPDFService
from src.services.ricevute.date_utils import (
    emission_to_rome,
    normalize_emission_datetime,
    resolve_order_payment_date,
)
from src.services.ricevute.order_lines import (
    build_shipping_line_dict,
    load_order_shipping,
    load_product_weights,
    resolve_line_product_weight,
    resolve_order_total_weight,
    resolve_shipping_amounts,
)
from src.services.ricevute.pdf_storage import (
    delete_ricevuta_pdf_file,
    read_ricevuta_pdf_bytes,
    update_ricevuta_pdf_metadata,
)
from src.services.routers.order_document_service import OrderDocumentService

EXPORT_MAX_LIMIT = 5000


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), 2)


def _order_is_modifiable(order: Order) -> bool:
    return order.id_order_state != ORDER_STATE_SPEDIZIONE_CONFERMATA


class RicevutaService(IRicevutaService):
    def __init__(
        self,
        ricevuta_repository: IRicevutaRepository,
        order_repository: IOrderRepository,
        order_detail_repository: IOrderDetailRepository,
        customer_repository: ICustomerRepository,
        address_repository: IAddressRepository,
    ):
        self._ricevuta_repository = ricevuta_repository
        self._order_repository = order_repository
        self._order_detail_repository = order_detail_repository
        self._customer_repository = customer_repository
        self._address_repository = address_repository
        self._pdf_service = RicevutaPDFService()
        self._export_service = RicevutaExportService()

    @property
    def _session(self):
        return self._ricevuta_repository._session

    def create_ricevuta(
        self, data: RicevutaCreateSchema, user_id: Optional[int] = None
    ) -> RicevutaResponseSchema:
        order = self._get_order_or_raise(data.id_order)
        self._ensure_order_not_invoiced(order.id_order)
        self._ensure_no_active_ricevuta(order.id_order)

        if not order.id_customer:
            raise ValidationException(
                "Ordine senza cliente collegato",
                details={"id_order": order.id_order},
            )

        try:
            data_incasso = resolve_order_payment_date(order)
        except ValueError as exc:
            raise ValidationException(str(exc), details={"id_order": order.id_order})

        data_emissione = normalize_emission_datetime(data.data_emissione)
        anno = emission_to_rome(data_emissione).year
        numero = self._ricevuta_repository.get_next_numero(anno)

        ricevuta = Ricevuta(
            numero=numero,
            anno=anno,
            id_order=order.id_order,
            id_customer=order.id_customer,
            data_incasso=data_incasso,
            data_emissione=data_emissione,
            stato=RicevutaStato.EMESSA,
        )
        created = self._ricevuta_repository.create(ricevuta)
        try:
            self._generate_and_persist_pdf(created, order)
        except Exception as exc:
            try:
                self._ricevuta_repository.delete(created.id_ricevuta)
            except Exception:
                pass
            raise ValidationException(
                f"Errore generazione PDF ricevuta: {exc}",
                details={"id_order": order.id_order},
            )
        return self.get_ricevuta(created.id_ricevuta)

    def update_ricevuta(
        self,
        id_ricevuta: int,
        data: RicevutaUpdateSchema,
        user_id: Optional[int] = None,
    ) -> RicevutaResponseSchema:
        ricevuta = self._ricevuta_repository.get_by_id_or_raise(id_ricevuta)
        self._ensure_ricevuta_emessa(ricevuta)

        order = self._get_order_or_raise(ricevuta.id_order)

        ricevuta.data_emissione = normalize_emission_datetime(data.data_emissione)
        if emission_to_rome(ricevuta.data_emissione).year != ricevuta.anno:
            ricevuta.anno = emission_to_rome(ricevuta.data_emissione).year
        self._ricevuta_repository.update(ricevuta)
        self._generate_and_persist_pdf(ricevuta, order)
        return self.get_ricevuta(id_ricevuta)

    def delete_ricevuta(
        self, id_ricevuta: int, user_id: Optional[int] = None
    ) -> None:
        ricevuta = self._ricevuta_repository.get_by_id_or_raise(id_ricevuta)
        delete_ricevuta_pdf_file(ricevuta)
        self._ricevuta_repository.delete(id_ricevuta)

    def regenerate_pdf(self, id_ricevuta: int) -> bytes:
        ricevuta = self._ricevuta_repository.get_by_id_or_raise(id_ricevuta)
        self._ensure_ricevuta_emessa(ricevuta)
        order = self._load_order_for_pdf(ricevuta.id_order)
        return self._generate_and_persist_pdf(ricevuta, order)

    def get_ricevuta_pdf_bytes(
        self, id_ricevuta: int, *, regenerate: bool = False
    ) -> bytes:
        ricevuta = self._ricevuta_repository.get_by_id_or_raise(id_ricevuta)
        self._ensure_ricevuta_emessa(ricevuta)
        if regenerate:
            order = self._load_order_for_pdf(ricevuta.id_order)
            return self._generate_and_persist_pdf(ricevuta, order)
        try:
            return read_ricevuta_pdf_bytes(ricevuta)
        except FileNotFoundError:
            order = self._load_order_for_pdf(ricevuta.id_order)
            return self._generate_and_persist_pdf(ricevuta, order)

    def get_ricevuta(self, id_ricevuta: int) -> RicevutaResponseSchema:
        ricevuta = self._ricevuta_repository.get_by_id_or_raise(id_ricevuta)
        order = self._order_repository.get_by_id(ricevuta.id_order)
        if not order:
            raise NotFoundException("Order", ricevuta.id_order)

        customer = self._customer_repository.get_by_id(ricevuta.id_customer)
        shipping = load_order_shipping(self._session, order)
        raw_details = self._order_detail_repository.get_by_order_id(order.id_order)
        product_weights = load_product_weights(
            self._session,
            [
                detail.id_product
                for detail in raw_details
                if detail.id_product and not detail.id_order_document
            ],
        )
        order_details = self._build_order_details(
            order, shipping, raw_details, product_weights
        )
        is_modifiable = _order_is_modifiable(order)
        addresses = self._map_addresses(order)

        shipping_net, shipping_incl = resolve_shipping_amounts(order, shipping)

        return RicevutaResponseSchema(
            id_ricevuta=ricevuta.id_ricevuta,
            numero=ricevuta.numero,
            anno=ricevuta.anno,
            data_incasso=ricevuta.data_incasso,
            data_emissione=ricevuta.data_emissione,
            stato=RicevutaStatoSchema(ricevuta.stato.value),
            pdf_path=ricevuta.pdf_path,
            pdf_generated_at=ricevuta.pdf_generated_at,
            created_at=ricevuta.created_at,
            updated_at=ricevuta.updated_at,
            annullata_at=ricevuta.annullata_at,
            annullata_da_user_id=ricevuta.annullata_da_user_id,
            is_modifiable=is_modifiable,
            id_order=order.id_order,
            order_reference=order.reference,
            id_order_state=order.id_order_state,
            total_weight=resolve_order_total_weight(
                order, raw_details, shipping, product_weights
            ),
            vies_status=order.vies_status,
            is_payed=bool(order.is_payed),
            payment_due_date=order.payment_due_date,
            payment=map_ricevuta_payment_embed(self._session, order.id_payment),
            shipping=map_ricevuta_shipping_embed(self._session, shipping),
            total_price_with_tax=_to_float(order.total_price_with_tax) or 0.0,
            total_price_net=_to_float(order.total_price_net),
            products_total_price_with_tax=_to_float(
                order.products_total_price_with_tax
            ),
            products_total_price_net=_to_float(order.products_total_price_net),
            shipping_total_price_with_tax=shipping_incl if shipping_incl else None,
            shipping_total_price_net=shipping_net if shipping_net else None,
            total_discounts=_to_float(order.total_discounts),
            customer=self._map_customer(customer),
            address_delivery=addresses["address_delivery"],
            address_invoice=addresses["address_invoice"],
            order_details=order_details,
        )

    def list_ricevute(self, filters: RicevutaFiltersSchema) -> RicevutaListResponseSchema:
        stato_value = filters.stato.value if filters.stato else None
        rows, total = self._ricevuta_repository.list_filtered(
            id_order=filters.id_order,
            id_customer=filters.id_customer,
            stato=stato_value,
            data_emissione_from=filters.data_emissione_from,
            data_emissione_to=filters.data_emissione_to,
            page=filters.page,
            limit=filters.limit,
        )

        items: List[RicevutaListItemSchema] = []
        for ricevuta in rows:
            customer = self._customer_repository.get_by_id(ricevuta.id_customer)
            order = self._order_repository.get_by_id(ricevuta.id_order)
            items.append(
                RicevutaListItemSchema(
                    id_ricevuta=ricevuta.id_ricevuta,
                    numero=ricevuta.numero,
                    anno=ricevuta.anno,
                    id_order=ricevuta.id_order,
                    data_incasso=ricevuta.data_incasso,
                    data_emissione=ricevuta.data_emissione,
                    stato=RicevutaStatoSchema(ricevuta.stato.value),
                    pdf_path=ricevuta.pdf_path,
                    pdf_generated_at=ricevuta.pdf_generated_at,
                    customer=self._map_customer(customer),
                    order_reference=order.reference if order else None,
                    order_total_with_tax=_to_float(order.total_price_with_tax)
                    if order
                    else None,
                )
            )

        return RicevutaListResponseSchema(
            ricevute=items,
            total=total,
            page=filters.page,
            limit=filters.limit,
        )

    def export_ricevuta(self, id_ricevuta: int, fmt: str) -> tuple[bytes, str, str]:
        export_fmt = self._parse_export_format(fmt)
        detail = self.get_ricevuta(id_ricevuta)
        if export_fmt == RicevutaExportFormatSchema.CSV:
            content = self._export_service.build_detail_csv(detail)
            media_type = "text/csv; charset=utf-8"
            extension = "csv"
        else:
            content = self._export_service.build_detail_xlsx(detail)
            media_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            extension = "xlsx"
        filename = f"Ricevuta-{detail.numero}-{detail.anno}.{extension}"
        return content, media_type, filename

    def export_ricevute(
        self, filters: RicevutaFiltersSchema, fmt: str
    ) -> tuple[bytes, str, str]:
        export_fmt = self._parse_export_format(fmt)
        export_filters = filters.model_copy(
            update={"page": 1, "limit": EXPORT_MAX_LIMIT}
        )
        listed = self.list_ricevute(export_filters)
        if listed.total > EXPORT_MAX_LIMIT:
            raise ValidationException(
                f"Troppi record per export ({listed.total}); restringere i filtri "
                f"(max {EXPORT_MAX_LIMIT})",
                details={"total": listed.total, "max": EXPORT_MAX_LIMIT},
            )

        if export_fmt == RicevutaExportFormatSchema.CSV:
            content = self._export_service.build_list_csv(listed.ricevute)
            media_type = "text/csv; charset=utf-8"
            extension = "csv"
        else:
            content = self._export_service.build_list_xlsx(listed.ricevute)
            media_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            extension = "xlsx"

        suffix = ""
        if filters.data_emissione_from and filters.data_emissione_to:
            suffix = (
                f"-{filters.data_emissione_from.isoformat()}"
                f"-{filters.data_emissione_to.isoformat()}"
            )
        elif filters.data_emissione_from:
            suffix = f"-from-{filters.data_emissione_from.isoformat()}"
        elif filters.data_emissione_to:
            suffix = f"-to-{filters.data_emissione_to.isoformat()}"
        filename = f"ricevute-export{suffix}.{extension}"
        return content, media_type, filename

    @staticmethod
    def _parse_export_format(fmt: str) -> RicevutaExportFormatSchema:
        normalized = (fmt or "").strip().lower()
        try:
            return RicevutaExportFormatSchema(normalized)
        except ValueError as exc:
            raise ValidationException(
                "Formato export non valido: usare csv o xlsx",
                details={"fmt": fmt},
            ) from exc

    def _build_order_details(
        self,
        order: Order,
        shipping=None,
        raw_details: Optional[List[OrderDetail]] = None,
        product_weights: Optional[dict[int, float]] = None,
    ) -> List[RicevutaOrderDetailEmbedSchema]:
        details = (
            raw_details
            if raw_details is not None
            else self._order_detail_repository.get_by_order_id(order.id_order)
        )
        order_details: List[RicevutaOrderDetailEmbedSchema] = []
        for detail in details:
            if detail.id_order_document:
                continue
            order_details.append(
                self._map_order_detail(detail, product_weights)
            )

        if shipping is None:
            shipping = load_order_shipping(self._session, order)
        shipping_line = build_shipping_line_dict(order, shipping)
        if shipping_line:
            order_details.append(
                RicevutaOrderDetailEmbedSchema(**shipping_line)
            )
        return order_details

    @staticmethod
    def _map_order_detail(
        detail: OrderDetail,
        product_weights: Optional[dict[int, float]] = None,
    ) -> RicevutaOrderDetailEmbedSchema:
        line_weight = resolve_line_product_weight(detail, product_weights)
        return RicevutaOrderDetailEmbedSchema(
            id_order_detail=detail.id_order_detail,
            id_product=detail.id_product,
            product_name=detail.product_name,
            product_reference=detail.product_reference,
            product_qty=detail.product_qty or 0,
            product_weight=_to_float(line_weight) if line_weight is not None else None,
            id_tax=detail.id_tax,
            unit_price_net=_to_float(detail.unit_price_net),
            unit_price_with_tax=_to_float(detail.unit_price_with_tax),
            total_price_net=_to_float(detail.total_price_net),
            total_price_with_tax=_to_float(detail.total_price_with_tax),
            reduction_percent=_to_float(detail.reduction_percent),
            reduction_amount=_to_float(detail.reduction_amount),
            is_shipping=False,
        )

    @staticmethod
    def _map_customer(customer) -> Optional[RicevutaCustomerEmbedSchema]:
        if not customer:
            return None
        return RicevutaCustomerEmbedSchema(
            id_customer=customer.id_customer,
            firstname=customer.firstname,
            lastname=customer.lastname,
            email=customer.email,
        )

    def _map_addresses(self, order: Order) -> dict:
        delivery_id = order.id_address_delivery
        invoice_id = order.id_address_invoice
        return {
            "address_delivery": self._map_address_embed(delivery_id),
            "address_invoice": self._map_address_embed(invoice_id),
        }

    def _map_address_embed(
        self, id_address: Optional[int]
    ) -> Optional[RicevutaAddressEmbedSchema]:
        if not id_address:
            return None
        address = self._address_repository.get_by_id(id_address)
        if not address:
            return None
        country = None
        if address.country:
            country = RicevutaCountryEmbedSchema(
                iso_code=address.country.iso_code,
                name=address.country.name,
            )
        return RicevutaAddressEmbedSchema(
            id_address=address.id_address,
            company=address.company,
            firstname=address.firstname,
            lastname=address.lastname,
            address1=address.address1,
            address2=address.address2,
            city=address.city,
            postcode=address.postcode,
            state=address.state,
            phone=address.phone,
            vat=address.vat,
            country=country,
        )

    def _get_order_or_raise(self, id_order: int) -> Order:
        order = self._order_repository.get_by_id(id_order)
        if not order:
            raise NotFoundException("Order", id_order)
        return order

    def _load_order_for_pdf(self, id_order: int) -> Order:
        order = (
            self._session.query(Order)
            .options(joinedload(Order.shipments))
            .filter(Order.id_order == id_order)
            .first()
        )
        if not order:
            raise NotFoundException("Order", id_order)
        return order

    @staticmethod
    def _ensure_ricevuta_emessa(ricevuta: Ricevuta) -> None:
        if ricevuta.stato != RicevutaStato.EMESSA:
            raise BusinessRuleException(
                "La ricevuta è già annullata",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"id_ricevuta": ricevuta.id_ricevuta, "stato": ricevuta.stato.value},
            )

    def _ensure_no_active_ricevuta(self, id_order: int) -> None:
        existing = self._ricevuta_repository.get_by_order_id(id_order)
        if existing:
            raise BusinessRuleException(
                "Esiste già una ricevuta emessa per questo ordine",
                ErrorCode.ALREADY_EXISTS,
                {"id_order": id_order, "id_ricevuta": existing.id_ricevuta},
            )

    def _ensure_order_not_invoiced(self, id_order: int) -> None:
        if OrderDocumentService(self._session).check_order_invoiced(id_order):
            raise BusinessRuleException(
                "Impossibile emettere ricevuta: ordine già fatturato",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"id_order": id_order},
            )

    def _generate_and_persist_pdf(self, ricevuta: Ricevuta, order: Order) -> bytes:
        order_for_pdf = order
        if not hasattr(order, "shipments") or (
            order.shipments is None and order.id_shipping
        ):
            order_for_pdf = self._load_order_for_pdf(order.id_order)
        pdf_bytes = self._pdf_service.generate_ricevuta_pdf(
            self._session, ricevuta, order_for_pdf
        )
        update_ricevuta_pdf_metadata(ricevuta, pdf_bytes)
        self._ricevuta_repository.update(ricevuta)
        return pdf_bytes
