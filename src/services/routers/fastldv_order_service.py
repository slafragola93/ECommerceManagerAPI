"""
Servizio FastLDV: ordine unificato (dati + validazione) e notify-print.
"""
import logging
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from src.core.exceptions import BusinessRuleException, ErrorCode, NotFoundException
from src.core.settings import get_fastldv_settings
from src.events.core.event import Event, EventType
from src.events.runtime import emit_event
from src.models.address import Address
from src.models.carrier_api import CarrierApi
from src.models.country import Country
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.order_package import OrderPackage
from src.models.relations.relations import orders_history
from src.models.shipping import Shipping
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.repository.interfaces.order_detail_repository_interface import IOrderDetailRepository
from src.repository.interfaces.order_repository_interface import IOrderRepository
from src.repository.interfaces.shipping_repository_interface import IShippingRepository
from src.schemas.fastldv_schema import (
    FastLdvCarrierSchema,
    FastLdvDocumentSchema,
    FastLdvLegacySchema,
    FastLdvLineSchema,
    FastLdvNotifyPrintRequestSchema,
    FastLdvNotifyPrintResponseSchema,
    FastLdvOrderDataSchema,
    FastLdvShippingSchema,
    FastLdvValidationSchema,
)
from src.services.interfaces.fastldv_order_service_interface import IFastLdvOrderService

logger = logging.getLogger(__name__)

ORDER_STATE_CANCELED = 5
ORDER_STATE_SHIPPED = 3
ORDER_STATE_SHIPPING_CONFIRMED = 4
ORDER_STATE_READY = 2
ORDER_STATE_PREPARING = 1
ORDER_STATE_MULTISHIPPING = 7
ORDER_STATE_WAITING = 6

LABEL_REPRINT_MESSAGE = (
    "⚠️ Attenzione: Stai effettuando la ristampa di una etichetta già stampata "
    "precedentemente. Fare un ulteriore controllo. ⚠️"
)


class FastLdvOrderService(IFastLdvOrderService):
    """Business logic per integrazione app magazzino FastLDV."""

    def __init__(
        self,
        session: Session,
        order_repository: IOrderRepository,
        order_detail_repository: IOrderDetailRepository,
        shipping_repository: IShippingRepository,
        api_carrier_repository: IApiCarrierRepository,
    ):
        self._session = session
        self._order_repository = order_repository
        self._order_detail_repository = order_detail_repository
        self._shipping_repository = shipping_repository
        self._api_carrier_repository = api_carrier_repository

    def get_order_context(
        self,
        id_origin: int,
        carrier_query: Optional[str] = None,
        printer: Optional[str] = None,
        id_store: Optional[int] = None,
        skip_log: bool = False,
        include_legacy: bool = True,
    ) -> Tuple[FastLdvOrderDataSchema, bool]:
        order = self._resolve_order(id_origin, id_store)
        label_code = self._fastldv_label_code(order)
        db_id_origin = self._db_id_origin(order)

        shipping = self._load_shipping(order)
        carrier_api = self._load_carrier_api(shipping)
        if not carrier_api:
            raise BusinessRuleException(
                "Corriere non assegnato",
                error_code=ErrorCode.CARRIER_NOT_ASSIGNED,
                details={"code": id_origin, "id_order": order.id_order},
            )

        if carrier_query and carrier_api.name.lower() != carrier_query.lower():
            logger.warning(
                "FastLDV carrier mismatch for code=%s id_order=%s: query=%r order=%r",
                id_origin,
                order.id_order,
                carrier_query,
                carrier_api.name,
            )

        if printer and not skip_log:
            logger.info(
                "FastLDV order lookup code=%s id_order=%s printer=%r",
                id_origin,
                order.id_order,
                printer,
            )

        lines = self._build_lines(order.id_order)
        shipping_data = self._build_shipping_data(order, shipping)
        carrier_data = FastLdvCarrierSchema(
            id_carrier_api=carrier_api.id_carrier_api,
            name=carrier_api.name,
            layout_type=self._resolve_layout_type(carrier_api),
        )
        document = FastLdvDocumentSchema(num_doc=str(label_code))
        validation = self._validate_order(order, shipping, id_origin)

        data = FastLdvOrderDataSchema(
            id_origin=db_id_origin,
            id_order=order.id_order,
            carrier=carrier_data,
            shipping=shipping_data,
            document=document,
            lines=lines,
            validation=validation,
        )

        if include_legacy:
            data.legacy = FastLdvLegacySchema(
                id_doc=label_code,
                corrieri_id_carrier=carrier_api.id_carrier_api,
                corrieri_carrier=carrier_api.name,
                corrieri_tracking=shipping_data.tracking,
                corrieri_layout_type=carrier_data.layout_type,
                intDoc={"num_doc": str(label_code)},
            )

        return data, validation.printable

    def notify_print(
        self, request: FastLdvNotifyPrintRequestSchema
    ) -> FastLdvNotifyPrintResponseSchema:
        order = self._resolve_order(request.id_origin, request.id_store)
        db_id_origin = self._db_id_origin(order)

        id_shipping = self._resolve_id_shipping_for_notify(order)
        if not id_shipping:
            raise NotFoundException(
                "Shipping",
                None,
                {"code": request.id_origin, "reason": "Nessuna spedizione associata"},
            )

        tracking = request.tracking.strip()
        self._shipping_repository.update_tracking(id_shipping, tracking)
        self._session.commit()

        logger.info(
            "FastLDV notify-print code=%s id_origin_db=%s id_order=%s id_shipping=%s tracking=%r",
            request.id_origin,
            db_id_origin,
            order.id_order,
            id_shipping,
            tracking,
        )
        return FastLdvNotifyPrintResponseSchema(
            data={
                "id_origin": db_id_origin,
                "id_order": order.id_order,
                "id_shipping": id_shipping,
                "tracking": tracking,
                "awb": tracking or None,
            }
        )

    def _resolve_order(self, code: int, id_store: Optional[int] = None) -> Order:
        order = self._order_repository.get_by_fastldv_code(code, id_store)
        if not order:
            raise NotFoundException(
                "Order",
                code,
                {"code": code, "id_store": id_store},
            )
        return order

    @staticmethod
    def _db_id_origin(order: Order) -> int:
        """Valore reale `orders.id_origin` (0 se ordine nato nel gestionale)."""
        return int(order.id_origin or 0)

    @staticmethod
    def _fastldv_label_code(order: Order) -> int:
        """Codice su etichetta/documento: id_origin PS, oppure id_order se gestionale."""
        if order.id_origin and order.id_origin != 0:
            return int(order.id_origin)
        return int(order.id_order)

    def _load_shipping(self, order: Order) -> Optional[Shipping]:
        id_shipping = order.id_shipping
        if not id_shipping:
            return None
        return self._session.query(Shipping).filter(Shipping.id_shipping == id_shipping).first()

    def _load_carrier_api(self, shipping: Optional[Shipping]) -> Optional[CarrierApi]:
        if not shipping or not shipping.id_carrier_api:
            return None
        return (
            self._session.query(CarrierApi)
            .options(joinedload(CarrierApi.brt_configuration))
            .filter(CarrierApi.id_carrier_api == shipping.id_carrier_api)
            .first()
        )

    def _build_lines(self, id_order: int) -> List[FastLdvLineSchema]:
        details = self._order_detail_repository.get_by_order_id(id_order)
        lines: List[FastLdvLineSchema] = []
        for detail in details:
            if detail.id_order_document:
                continue
            name = (detail.product_name or "").strip()
            if name.lower().startswith("buono sconto"):
                continue
            lines.append(
                FastLdvLineSchema(
                    quantity=int(detail.product_qty or 0),
                    sku=(detail.product_reference or "").strip(),
                    name=name,
                )
            )
        return lines

    def _build_shipping_data(
        self, order: Order, shipping: Optional[Shipping]
    ) -> FastLdvShippingSchema:
        colli = self._count_colli(order.id_order)
        peso = 0.0
        tracking = ""
        if shipping:
            peso = float(shipping.weight or 0)
            tracking = (shipping.tracking or "").strip()
        if peso <= 0 and order.total_weight:
            peso = float(order.total_weight)

        contrassegno = self._format_money(order.cash_on_delivery)
        country_iso = self._resolve_country_iso(order.id_address_delivery)

        return FastLdvShippingSchema(
            colli=colli,
            peso=peso,
            contrassegno=contrassegno,
            tracking=tracking,
            country_iso=country_iso,
        )

    def _count_colli(self, id_order: int) -> int:
        count = (
            self._session.query(OrderPackage)
            .filter(OrderPackage.id_order == id_order)
            .count()
        )
        return max(count, 1)

    def _resolve_country_iso(self, id_address_delivery: Optional[int]) -> str:
        if not id_address_delivery:
            return "IT"
        row = (
            self._session.query(Country.iso_code)
            .join(Address, Address.id_country == Country.id_country)
            .filter(Address.id_address == id_address_delivery)
            .first()
        )
        if row and row.iso_code:
            return row.iso_code.upper()
        return "IT"

    def _resolve_layout_type(self, carrier_api: CarrierApi) -> str:
        fmt = ""
        if hasattr(carrier_api, "brt_configuration") and carrier_api.brt_configuration:
            fmt = (carrier_api.brt_configuration.label_format or "").lower()
        if "zpl" in fmt or "zebra" in fmt:
            return "zebra"
        if "pdf" in fmt:
            return "pdf"
        if carrier_api.carrier_type and carrier_api.carrier_type.value == "BRT":
            return "zebra"
        return "pdf"

    def _validate_order(
        self, order: Order, shipping: Optional[Shipping], id_origin: int
    ) -> FastLdvValidationSchema:
        settings = get_fastldv_settings()
        if id_origin in settings.get_bypass_ids():
            return FastLdvValidationSchema(
                printable=True,
                severity="ok",
                code="BYPASS",
                message="OK",
            )

        if order.id_order_state == ORDER_STATE_CANCELED:
            return self._error_validation("ORDER_CANCELED", "Ordine annullato")

        if self._is_order_locked(order):
            return self._error_validation("ORDER_LOCKED", "Ordine bloccato")

        if not order.is_payed:
            return self._error_validation("ORDER_NOT_PAID", "Ordine non pagato")

        if order.id_order_state in (ORDER_STATE_SHIPPED, ORDER_STATE_SHIPPING_CONFIRMED):
            return self._error_validation("ORDER_ALREADY_SHIPPED", "Ordine già spedito")

        if not self._is_ready_for_warehouse(order):
            return self._error_validation(
                "ORDER_NOT_READY",
                "Ordine non ancora in lavorazione, non puoi stampare",
            )

        tracking = (shipping.tracking if shipping else "") or ""
        if tracking.strip():
            return FastLdvValidationSchema(
                printable=True,
                severity="warning",
                code="LABEL_ALREADY_PRINTED",
                message=LABEL_REPRINT_MESSAGE,
            )

        return FastLdvValidationSchema(
            printable=True,
            severity="ok",
            code="OK",
            message="OK",
        )

    def _is_order_locked(self, order: Order) -> bool:
        """Nessun flag locked nel modello: In Attesa trattato come blocco operativo."""
        return order.id_order_state == ORDER_STATE_WAITING

    def _is_ready_for_warehouse(self, order: Order) -> bool:
        """
        Equivalente Smarty ready==1 AND shipped==1:
        - ready: stato Pronti (2) o Multispedizione (7), o già passato da stato 2
        - shipped: in lavorazione magazzino (1, 2, 7)
        """
        state = order.id_order_state
        in_processing = state in (
            ORDER_STATE_PREPARING,
            ORDER_STATE_READY,
            ORDER_STATE_MULTISHIPPING,
        )
        is_ready = state in (ORDER_STATE_READY, ORDER_STATE_MULTISHIPPING) or (
            self._was_in_state(order.id_order, ORDER_STATE_READY)
        )
        return in_processing and is_ready

    def _was_in_state(self, id_order: int, id_order_state: int) -> bool:
        row = (
            self._session.query(orders_history)
            .filter(
                orders_history.c.id_order == id_order,
                orders_history.c.id_order_state == id_order_state,
            )
            .first()
        )
        return row is not None

    def _error_validation(self, code: str, message: str) -> FastLdvValidationSchema:
        return FastLdvValidationSchema(
            printable=False,
            severity="error",
            code=code,
            message=message,
        )

    def _resolve_id_shipping_for_notify(self, order: Order) -> Optional[int]:
        # Multispedizione (is_multishipping + documenti shipping multipli): accantonata in v1.
        # Si usa sempre la spedizione principale dell'ordine (orders.id_shipping).
        return order.id_shipping or self._order_repository.get_id_shipping_by_order_id(
            order.id_order
        )

    @staticmethod
    def _format_money(value) -> str:
        if value is None:
            return "0.00"
        amount = Decimal(str(value))
        return f"{amount:.2f}"
