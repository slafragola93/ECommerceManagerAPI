"""Service ricevute — lettura con join live ordine/cliente/order_details."""

from datetime import date, datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

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
    RicevutaOrderEmbedSchema,
    RicevutaResponseSchema,
    RicevutaOrderDetailEmbedSchema,
    RicevutaStatoSchema,
    RicevutaUpdateSchema,
)
from src.services.export.ricevuta_export_service import RicevutaExportService
from src.services.interfaces.ricevuta_service_interface import IRicevutaService
from src.services.pdf.ricevuta_pdf_service import RicevutaPDFService
from src.services.ricevute.date_utils import resolve_order_payment_date
from src.services.ricevute.pdf_storage import (
    read_ricevuta_pdf_bytes,
    update_ricevuta_pdf_metadata,
)
from src.services.routers.order_document_service import OrderDocumentService

ROME = ZoneInfo("Europe/Rome")
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
        self._ensure_order_modifiable(order)
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

        data_emissione = data.data_emissione or datetime.now(ROME).date()
        anno = data_emissione.year
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
        self._ensure_order_modifiable(order)

        ricevuta.data_emissione = data.data_emissione
        if data.data_emissione.year != ricevuta.anno:
            ricevuta.anno = data.data_emissione.year
        self._ricevuta_repository.update(ricevuta)
        self._generate_and_persist_pdf(ricevuta, order)
        return self.get_ricevuta(id_ricevuta)

    def annulla_ricevuta(
        self, id_ricevuta: int, user_id: Optional[int] = None
    ) -> RicevutaResponseSchema:
        ricevuta = self._ricevuta_repository.get_by_id_or_raise(id_ricevuta)
        self._ensure_ricevuta_emessa(ricevuta)

        order = self._get_order_or_raise(ricevuta.id_order)
        self._ensure_order_modifiable(order)

        ricevuta.stato = RicevutaStato.ANNULLATA
        ricevuta.annullata_at = datetime.utcnow()
        ricevuta.annullata_da_user_id = user_id
        self._ricevuta_repository.update(ricevuta)
        return self.get_ricevuta(id_ricevuta)

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
        order_details = self._build_order_details(order.id_order)
        is_modifiable = _order_is_modifiable(order)
        addresses = self._map_addresses(order)

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
            customer=self._map_customer(customer),
            order=self._map_order(order),
            address=addresses.get("address"),
            address_delivery=addresses.get("address_delivery"),
            address_invoice=addresses.get("address_invoice"),
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

    def _build_order_details(self, id_order: int) -> List[RicevutaOrderDetailEmbedSchema]:
        details = self._order_detail_repository.get_by_order_id(id_order)
        order_details: List[RicevutaOrderDetailEmbedSchema] = []
        for detail in details:
            if detail.id_order_document:
                continue
            order_details.append(self._map_order_detail(detail))
        return order_details

    @staticmethod
    def _map_order_detail(detail: OrderDetail) -> RicevutaOrderDetailEmbedSchema:
        return RicevutaOrderDetailEmbedSchema(
            id_order_detail=detail.id_order_detail,
            id_product=detail.id_product,
            product_name=detail.product_name,
            product_reference=detail.product_reference,
            product_qty=detail.product_qty or 0,
            id_tax=detail.id_tax,
            unit_price_net=_to_float(detail.unit_price_net),
            unit_price_with_tax=_to_float(detail.unit_price_with_tax),
            total_price_net=_to_float(detail.total_price_net),
            total_price_with_tax=_to_float(detail.total_price_with_tax),
            reduction_percent=_to_float(detail.reduction_percent),
            reduction_amount=_to_float(detail.reduction_amount),
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

    @staticmethod
    def _map_order(order: Order) -> RicevutaOrderEmbedSchema:
        return RicevutaOrderEmbedSchema(
            id_order=order.id_order,
            reference=order.reference,
            id_order_state=order.id_order_state,
            is_payed=bool(order.is_payed),
            payment_date=order.payment_date,
            total_price_with_tax=_to_float(order.total_price_with_tax) or 0.0,
            total_price_net=_to_float(order.total_price_net),
            products_total_price_with_tax=_to_float(order.products_total_price_with_tax),
            products_total_price_net=_to_float(order.products_total_price_net),
            total_discounts=_to_float(order.total_discounts),
            general_note=order.general_note,
        )

    def _map_addresses(self, order: Order) -> dict:
        delivery_id = order.id_address_delivery
        invoice_id = order.id_address_invoice
        if delivery_id and delivery_id == invoice_id:
            return {"address": self._map_address_embed(delivery_id)}
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
    def _ensure_order_modifiable(order: Order) -> None:
        if not _order_is_modifiable(order):
            raise BusinessRuleException(
                "Operazione non consentita: ordine in Spedizione Confermata",
                ErrorCode.ORDER_NOT_MODIFIABLE,
                {"id_order": order.id_order, "id_order_state": order.id_order_state},
            )

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
