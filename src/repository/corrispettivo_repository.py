from __future__ import annotations

import calendar
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import exists, func, literal, or_, select, union_all
from sqlalchemy.orm import Session

from src.models.address import Address
from src.models.country import Country
from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.ricevuta import Ricevuta, RicevutaStato
from src.models.shipping import Shipping
from src.models.tax import Tax
from src.services.corrispettivi.aggregation import MovementRow, decimal_or_zero


class CorrispettivoRepository:
    TIMEZONE = "Europe/Rome"
    SALES_COMPONENT_BASE = "base"
    SALES_COMPONENT_RICEVUTE_DECURTAZIONE = "ricevute_decurtazione"
    SALES_COMPONENT_RICEVUTE_IMPUTAZIONE = "ricevute_imputazione"

    def __init__(self, session: Session):
        self._session = session

    def _no_invoice_filter(self):
        """Ordine non fatturato: nessun FiscalDocument invoice collegato."""
        return ~exists(
            select(FiscalDocument.id_fiscal_document).where(
                FiscalDocument.id_order == Order.id_order,
                FiscalDocument.document_type == "invoice",
            )
        ).correlate(Order)

    def _has_credit_note_filter(self):
        """Ordine con almeno una nota di credito collegata."""
        return exists(
            select(FiscalDocument.id_fiscal_document).where(
                FiscalDocument.id_order == Order.id_order,
                FiscalDocument.document_type == "credit_note",
            )
        ).correlate(Order)

    def _order_day_expr(self):
        return self._local_day_expr(Order.date_add)

    def _ricevuta_emission_day_expr(self):
        return self._local_day_expr(Ricevuta.data_emissione)

    def _has_deferred_ricevuta_filter(self):
        """Ordine con ricevuta emessa in giorno diverso da date_add (spostamento corrispettivo)."""
        order_day = self._order_day_expr()
        emission_day = self._ricevuta_emission_day_expr()
        return exists(
            select(Ricevuta.id_ricevuta).where(
                Ricevuta.id_order == Order.id_order,
                Ricevuta.stato == RicevutaStato.EMESSA,
                emission_day != order_day,
            )
        ).correlate(Order)

    def _corrispettivi_sales_order_filters(self):
        """Vendite corrispettivi: ordini non fatturati, pagati; esclusi solo se ricevuta differita."""
        return (
            self._no_invoice_filter(),
            Order.is_payed.is_(True),
            ~self._has_deferred_ricevuta_filter(),
        )

    def _ricevuta_order_eligibility_filters(self):
        """Ordine eleggibile sotto una ricevuta emessa (stesse regole vendite)."""
        return (
            self._no_invoice_filter(),
            Order.is_payed.is_(True),
        )

    def _corrispettivi_return_order_filters(self):
        """Resi corrispettivi: ordine pagato e (non fatturato oppure con nota di credito)."""
        return (
            Order.is_payed.is_(True),
            or_(
                self._no_invoice_filter(),
                self._has_credit_note_filter(),
            ),
        )

    def _period_bounds(self, year: int, month: int, day: Optional[int] = None) -> tuple[date, date]:
        if day is not None:
            start = date(year, month, day)
            return start, start
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)

    def _local_day_expr(self, column):
        converted = func.convert_tz(column, "+00:00", self.TIMEZONE)
        return func.coalesce(func.date(converted), func.date(column))

    def _delivery_country_exists(self, iso_code: str):
        """Filtra ordini per paese di consegna senza richiedere join espliciti."""
        return exists(
            select(1)
            .select_from(Address)
            .join(Country, Address.id_country == Country.id_country)
            .where(
                Address.id_address == Order.id_address_delivery,
                func.upper(Country.iso_code) == iso_code.upper(),
            )
        ).correlate(Order)

    def _apply_order_filters(self, query, filters: Optional[dict]):
        if not filters:
            return query
        if filters.get("id_platform"):
            query = query.filter(Order.id_platform == filters["id_platform"])
        if filters.get("id_store"):
            query = query.filter(Order.id_store == filters["id_store"])
        if filters.get("delivery_country_iso"):
            query = query.filter(
                self._delivery_country_exists(filters["delivery_country_iso"])
            )
        return query

    @staticmethod
    def _as_date(value) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

    @staticmethod
    def _empty_gross_bucket() -> dict:
        return {
            "total_with_tax": Decimal("0"),
            "total_net": Decimal("0"),
            "products_with_tax": Decimal("0"),
            "products_net": Decimal("0"),
            "shipping_with_tax": Decimal("0"),
            "shipping_net": Decimal("0"),
        }

    @staticmethod
    def _gross_bucket_from_row(row) -> dict:
        products_with_tax = decimal_or_zero(row.products_with_tax)
        products_net = decimal_or_zero(row.products_net)
        total_with_tax = decimal_or_zero(row.total_with_tax)
        total_net = decimal_or_zero(row.total_net)
        return {
            "total_with_tax": total_with_tax,
            "total_net": total_net,
            "products_with_tax": products_with_tax,
            "products_net": products_net,
            "shipping_with_tax": total_with_tax - products_with_tax,
            "shipping_net": total_net - products_net,
        }

    @staticmethod
    def _add_gross_bucket(target: dict, source: dict) -> None:
        for key in target:
            target[key] += source.get(key, Decimal("0"))

    def fetch_sales_gross_breakdown_by_day(
        self,
        start_date: date,
        end_date: date,
        filters: Optional[dict] = None,
    ) -> Dict[date, dict]:
        """
        BE-3.2 — Vendite lorde per giorno con scomposizione audit (UNION ALL).

        Componenti per giorno:
        - `base`: ordini standard su Order.date_add (inclusi ordini con ricevuta same-day)
        - `ricevute_decurtazione`: negativo su Order.date_add se emissione ≠ date ordine
        - `ricevute_imputazione`: positivo su ricevute.data_emissione se emissione ≠ date ordine
        - `net`: somma dei tre
        """
        order_day = self._order_day_expr()
        emission_day = self._ricevuta_emission_day_expr()

        base_query = (
            self._session.query(
                order_day.label("movement_date"),
                literal(self.SALES_COMPONENT_BASE).label("component"),
                func.sum(Order.total_price_with_tax).label("total_with_tax"),
                func.sum(Order.total_price_net).label("total_net"),
                func.sum(Order.products_total_price_with_tax).label("products_with_tax"),
                func.sum(Order.products_total_price_net).label("products_net"),
            )
            .select_from(Order)
            .filter(
                *self._corrispettivi_sales_order_filters(),
                order_day >= start_date,
                order_day <= end_date,
            )
            .group_by(order_day)
        )
        base_query = self._apply_order_filters(base_query, filters)

        decurtazione_query = (
            self._session.query(
                order_day.label("movement_date"),
                literal(self.SALES_COMPONENT_RICEVUTE_DECURTAZIONE).label("component"),
                (-func.sum(Order.total_price_with_tax)).label("total_with_tax"),
                (-func.sum(Order.total_price_net)).label("total_net"),
                (-func.sum(Order.products_total_price_with_tax)).label("products_with_tax"),
                (-func.sum(Order.products_total_price_net)).label("products_net"),
            )
            .select_from(Ricevuta)
            .join(Order, Ricevuta.id_order == Order.id_order)
            .filter(
                Ricevuta.stato == RicevutaStato.EMESSA,
                emission_day != order_day,
                order_day >= start_date,
                order_day <= end_date,
                *self._ricevuta_order_eligibility_filters(),
            )
            .group_by(order_day)
        )
        decurtazione_query = self._apply_order_filters(decurtazione_query, filters)

        imputazione_query = (
            self._session.query(
                emission_day.label("movement_date"),
                literal(self.SALES_COMPONENT_RICEVUTE_IMPUTAZIONE).label("component"),
                func.sum(Order.total_price_with_tax).label("total_with_tax"),
                func.sum(Order.total_price_net).label("total_net"),
                func.sum(Order.products_total_price_with_tax).label("products_with_tax"),
                func.sum(Order.products_total_price_net).label("products_net"),
            )
            .select_from(Ricevuta)
            .join(Order, Ricevuta.id_order == Order.id_order)
            .filter(
                Ricevuta.stato == RicevutaStato.EMESSA,
                emission_day != order_day,
                emission_day >= start_date,
                emission_day <= end_date,
                *self._ricevuta_order_eligibility_filters(),
            )
            .group_by(emission_day)
        )
        imputazione_query = self._apply_order_filters(imputazione_query, filters)

        combined = union_all(
            base_query.statement,
            decurtazione_query.statement,
            imputazione_query.statement,
        ).alias("sales_gross_union")

        rows = self._session.query(combined).all()

        by_day: Dict[date, dict] = {}
        for row in rows:
            movement_date = self._as_date(row.movement_date)
            component = row.component
            bucket = by_day.setdefault(
                movement_date,
                {
                    self.SALES_COMPONENT_BASE: self._empty_gross_bucket(),
                    self.SALES_COMPONENT_RICEVUTE_DECURTAZIONE: self._empty_gross_bucket(),
                    self.SALES_COMPONENT_RICEVUTE_IMPUTAZIONE: self._empty_gross_bucket(),
                    "net": self._empty_gross_bucket(),
                },
            )
            gross = self._gross_bucket_from_row(row)
            self._add_gross_bucket(bucket[component], gross)
            self._add_gross_bucket(bucket["net"], gross)

        return by_day

    def _order_detail_line_filter(self):
        return or_(
            OrderDetail.id_order_document.is_(None),
            OrderDetail.id_order_document == 0,
        )

    def _append_ricevuta_movements(
        self,
        movements: List[MovementRow],
        start_date: date,
        end_date: date,
        filters: Optional[dict],
    ) -> None:
        """BE-3.1/3.2 — Aggiustamenti ricevuta via UNION ALL (prodotti + spedizione)."""
        movements.extend(
            self._fetch_ricevuta_adjustment_movements(start_date, end_date, filters)
        )

    def _fetch_ricevuta_adjustment_movements(
        self,
        start_date: date,
        end_date: date,
        filters: Optional[dict],
    ) -> List[MovementRow]:
        order_day = self._order_day_expr()
        emission_day = self._ricevuta_emission_day_expr()
        parts = []
        for movement_date_col, sign, use_order_day in (
            (order_day, -1, True),
            (emission_day, 1, False),
        ):
            ricevuta_filters = [
                Ricevuta.stato == RicevutaStato.EMESSA,
                emission_day != order_day,
                self._order_detail_line_filter(),
                *self._ricevuta_order_eligibility_filters(),
            ]
            ricevuta_filters.extend(
                [
                    movement_date_col >= start_date,
                    movement_date_col <= end_date,
                ]
            )

            product_part = (
                self._session.query(
                    movement_date_col.label("movement_date"),
                    Country.iso_code.label("country_iso"),
                    OrderDetail.id_tax.label("id_tax"),
                    (func.sum(OrderDetail.total_price_net) * sign).label("amount"),
                    literal(0).label("is_shipping"),
                )
                .select_from(Ricevuta)
                .join(Order, Ricevuta.id_order == Order.id_order)
                .join(OrderDetail, OrderDetail.id_order == Order.id_order)
                .outerjoin(Address, Order.id_address_delivery == Address.id_address)
                .outerjoin(Country, Address.id_country == Country.id_country)
                .filter(*ricevuta_filters)
                .group_by(movement_date_col, Country.iso_code, OrderDetail.id_tax)
            )
            product_part = self._apply_order_filters(product_part, filters)
            parts.append(product_part.statement)

            shipping_part = (
                self._session.query(
                    movement_date_col.label("movement_date"),
                    Country.iso_code.label("country_iso"),
                    Shipping.id_tax.label("id_tax"),
                    (func.sum(Shipping.price_tax_excl) * sign).label("amount"),
                    literal(1).label("is_shipping"),
                )
                .select_from(Ricevuta)
                .join(Order, Ricevuta.id_order == Order.id_order)
                .join(Shipping, Order.id_shipping == Shipping.id_shipping)
                .outerjoin(Address, Order.id_address_delivery == Address.id_address)
                .outerjoin(Country, Address.id_country == Country.id_country)
                .filter(
                    *ricevuta_filters,
                    Shipping.price_tax_excl.isnot(None),
                    Shipping.price_tax_excl > 0,
                )
                .group_by(movement_date_col, Country.iso_code, Shipping.id_tax)
            )
            shipping_part = self._apply_order_filters(shipping_part, filters)
            parts.append(shipping_part.statement)

        if not parts:
            return []

        combined = union_all(*parts).alias("ricevuta_movements_union")
        rows = self._session.query(combined).all()

        result: List[MovementRow] = []
        for row in rows:
            amount = decimal_or_zero(row.amount)
            if amount == 0:
                continue
            result.append(
                MovementRow(
                    movement_date=self._as_date(row.movement_date),
                    country_iso=row.country_iso,
                    id_tax=row.id_tax,
                    sales_net=amount,
                    is_shipping=bool(row.is_shipping),
                )
            )
        return result

    def fetch_movements(
        self,
        year: int,
        month: int,
        filters: Optional[dict] = None,
    ) -> List[MovementRow]:
        start_date, end_date = self._period_bounds(
            year, month, filters.get("day") if filters else None
        )
        movements: List[MovementRow] = []

        order_day = self._local_day_expr(Order.date_add)
        return_day = self._local_day_expr(FiscalDocument.date_add)

        sales_details = (
            self._session.query(
                order_day.label("movement_date"),
                Country.iso_code,
                OrderDetail.id_tax,
                func.sum(OrderDetail.total_price_net).label("amount"),
            )
            .join(Order, OrderDetail.id_order == Order.id_order)
            .outerjoin(Address, Order.id_address_delivery == Address.id_address)
            .outerjoin(Country, Address.id_country == Country.id_country)
            .filter(
                *self._corrispettivi_sales_order_filters(),
                order_day >= start_date,
                order_day <= end_date,
            )
            .group_by(order_day, Country.iso_code, OrderDetail.id_tax)
        )
        sales_details = self._apply_order_filters(sales_details, filters)

        for row in sales_details.all():
            amount = decimal_or_zero(row.amount)
            if amount == 0:
                continue
            movements.append(
                MovementRow(
                    movement_date=self._as_date(row.movement_date),
                    country_iso=row.iso_code,
                    id_tax=row.id_tax,
                    sales_net=amount,
                )
            )

        sales_shipping = (
            self._session.query(
                order_day.label("movement_date"),
                Country.iso_code,
                Shipping.id_tax,
                func.sum(Shipping.price_tax_excl).label("amount"),
            )
            .join(Order, Order.id_shipping == Shipping.id_shipping)
            .outerjoin(Address, Order.id_address_delivery == Address.id_address)
            .outerjoin(Country, Address.id_country == Country.id_country)
            .filter(
                *self._corrispettivi_sales_order_filters(),
                order_day >= start_date,
                order_day <= end_date,
                Shipping.price_tax_excl.isnot(None),
                Shipping.price_tax_excl > 0,
            )
            .group_by(order_day, Country.iso_code, Shipping.id_tax)
        )
        sales_shipping = self._apply_order_filters(sales_shipping, filters)

        for row in sales_shipping.all():
            amount = decimal_or_zero(row.amount)
            if amount == 0:
                continue
            movements.append(
                MovementRow(
                    movement_date=self._as_date(row.movement_date),
                    country_iso=row.iso_code,
                    id_tax=row.id_tax,
                    sales_net=amount,
                    is_shipping=True,
                )
            )

        return_details = (
            self._session.query(
                return_day.label("movement_date"),
                Country.iso_code,
                FiscalDocumentDetail.id_tax,
                func.sum(FiscalDocumentDetail.total_price_net).label("amount"),
            )
            .join(FiscalDocument, FiscalDocumentDetail.id_fiscal_document == FiscalDocument.id_fiscal_document)
            .join(Order, FiscalDocument.id_order == Order.id_order)
            .outerjoin(Address, Order.id_address_delivery == Address.id_address)
            .outerjoin(Country, Address.id_country == Country.id_country)
            .filter(
                FiscalDocument.document_type == "return",
                *self._corrispettivi_return_order_filters(),
                return_day >= start_date,
                return_day <= end_date,
            )
            .group_by(return_day, Country.iso_code, FiscalDocumentDetail.id_tax)
        )
        return_details = self._apply_order_filters(return_details, filters)

        for row in return_details.all():
            amount = decimal_or_zero(row.amount)
            if amount == 0:
                continue
            movements.append(
                MovementRow(
                    movement_date=self._as_date(row.movement_date),
                    country_iso=row.iso_code,
                    id_tax=row.id_tax,
                    returns_net=amount,
                )
            )

        return_shipping_rows = (
            self._session.query(
                FiscalDocument,
                return_day.label("movement_date"),
                Country.iso_code,
                Shipping.id_tax,
            )
            .join(Order, FiscalDocument.id_order == Order.id_order)
            .outerjoin(Address, Order.id_address_delivery == Address.id_address)
            .outerjoin(Country, Address.id_country == Country.id_country)
            .outerjoin(Shipping, Order.id_shipping == Shipping.id_shipping)
            .filter(
                FiscalDocument.document_type == "return",
                FiscalDocument.includes_shipping.is_(True),
                *self._corrispettivi_return_order_filters(),
                return_day >= start_date,
                return_day <= end_date,
            )
        )
        return_shipping_rows = self._apply_order_filters(return_shipping_rows, filters)

        for doc, movement_date, country_iso, shipping_tax_id in return_shipping_rows.all():
            products_net = decimal_or_zero(doc.products_total_price_net)
            total_net = decimal_or_zero(doc.total_price_net)
            shipping_net = total_net - products_net
            if shipping_net <= 0:
                continue
            movements.append(
                MovementRow(
                    movement_date=self._as_date(movement_date),
                    country_iso=country_iso,
                    id_tax=shipping_tax_id,
                    returns_net=shipping_net,
                    is_shipping=True,
                )
            )

        self._append_ricevuta_movements(movements, start_date, end_date, filters)

        return movements

    def get_taxes_by_ids(self, tax_ids: Set[int]) -> dict[int, Tax]:
        if not tax_ids:
            return {}
        taxes = self._session.query(Tax).filter(Tax.id_tax.in_(tax_ids)).all()
        return {tax.id_tax: tax for tax in taxes}

    def list_country_codes_with_movements(
        self,
        year: int,
        month: int,
        filters: Optional[dict] = None,
    ) -> List[str]:
        movements = self.fetch_movements(year, month, filters)
        codes = sorted(
            {
                (row.country_iso or "XX").upper()
                for row in movements
                if row.country_iso
            }
        )
        return codes

    def fetch_daily_counts(
        self,
        year: int,
        month: int,
        filters: Optional[dict] = None,
    ) -> Dict[date, Tuple[int, int]]:
        start_date, end_date = self._period_bounds(
            year, month, filters.get("day") if filters else None
        )
        order_day = self._local_day_expr(Order.date_add)
        return_day = self._local_day_expr(FiscalDocument.date_add)

        sales_query = (
            self._session.query(
                order_day.label("movement_date"),
                func.count(func.distinct(Order.id_order)).label("order_count"),
            )
            .select_from(Order)
            .filter(
                *self._corrispettivi_sales_order_filters(),
                order_day >= start_date,
                order_day <= end_date,
            )
            .group_by(order_day)
        )
        if filters:
            if filters.get("id_platform"):
                sales_query = sales_query.filter(Order.id_platform == filters["id_platform"])
            if filters.get("id_store"):
                sales_query = sales_query.filter(Order.id_store == filters["id_store"])
            if filters.get("delivery_country_iso"):
                sales_query = (
                    sales_query.outerjoin(Address, Order.id_address_delivery == Address.id_address)
                    .outerjoin(Country, Address.id_country == Country.id_country)
                    .filter(func.upper(Country.iso_code) == filters["delivery_country_iso"].upper())
                )

        returns_query = (
            self._session.query(
                return_day.label("movement_date"),
                func.count(func.distinct(FiscalDocument.id_fiscal_document)).label("return_count"),
            )
            .select_from(FiscalDocument)
            .join(Order, FiscalDocument.id_order == Order.id_order)
            .filter(
                FiscalDocument.document_type == "return",
                *self._corrispettivi_return_order_filters(),
                return_day >= start_date,
                return_day <= end_date,
            )
            .group_by(return_day)
        )
        if filters:
            if filters.get("id_platform"):
                returns_query = returns_query.filter(Order.id_platform == filters["id_platform"])
            if filters.get("id_store"):
                returns_query = returns_query.filter(Order.id_store == filters["id_store"])
            if filters.get("delivery_country_iso"):
                returns_query = (
                    returns_query.outerjoin(Address, Order.id_address_delivery == Address.id_address)
                    .outerjoin(Country, Address.id_country == Country.id_country)
                    .filter(func.upper(Country.iso_code) == filters["delivery_country_iso"].upper())
                )

        counts: Dict[date, Tuple[int, int]] = {}
        for row in sales_query.all():
            movement_date = self._as_date(row.movement_date)
            counts[movement_date] = (
                int(row.order_count or 0),
                counts.get(movement_date, (0, 0))[1],
            )

        ricevuta_sales_query = (
            self._session.query(
                self._ricevuta_emission_day_expr().label("movement_date"),
                func.count(func.distinct(Order.id_order)).label("order_count"),
            )
            .select_from(Ricevuta)
            .join(Order, Ricevuta.id_order == Order.id_order)
            .filter(
                Ricevuta.stato == RicevutaStato.EMESSA,
                self._ricevuta_emission_day_expr() >= start_date,
                self._ricevuta_emission_day_expr() <= end_date,
                *self._ricevuta_order_eligibility_filters(),
            )
            .group_by(self._ricevuta_emission_day_expr())
        )
        if filters:
            if filters.get("id_platform"):
                ricevuta_sales_query = ricevuta_sales_query.filter(
                    Order.id_platform == filters["id_platform"]
                )
            if filters.get("id_store"):
                ricevuta_sales_query = ricevuta_sales_query.filter(
                    Order.id_store == filters["id_store"]
                )
            if filters.get("delivery_country_iso"):
                ricevuta_sales_query = (
                    ricevuta_sales_query.outerjoin(
                        Address, Order.id_address_delivery == Address.id_address
                    )
                    .outerjoin(Country, Address.id_country == Country.id_country)
                    .filter(
                        func.upper(Country.iso_code)
                        == filters["delivery_country_iso"].upper()
                    )
                )

        for row in ricevuta_sales_query.all():
            movement_date = self._as_date(row.movement_date)
            existing = counts.get(movement_date, (0, 0))
            counts[movement_date] = (
                existing[0] + int(row.order_count or 0),
                existing[1],
            )

        for row in returns_query.all():
            movement_date = self._as_date(row.movement_date)
            existing = counts.get(movement_date, (0, 0))
            counts[movement_date] = (existing[0], int(row.return_count or 0))
        return counts

    def fetch_daily_gross_totals(
        self,
        year: int,
        month: int,
        filters: Optional[dict] = None,
    ) -> dict:
        start_date, end_date = self._period_bounds(
            year, month, filters.get("day") if filters else None
        )
        return_day = self._local_day_expr(FiscalDocument.date_add)

        sales_breakdown = self.fetch_sales_gross_breakdown_by_day(
            start_date, end_date, filters
        )

        returns_query = (
            self._session.query(
                return_day.label("movement_date"),
                func.sum(FiscalDocument.total_price_with_tax).label("total_with_tax"),
                func.sum(FiscalDocument.total_price_net).label("total_net"),
                func.sum(FiscalDocument.products_total_price_with_tax).label("products_with_tax"),
                func.sum(FiscalDocument.products_total_price_net).label("products_net"),
            )
            .select_from(FiscalDocument)
            .join(Order, FiscalDocument.id_order == Order.id_order)
            .filter(
                FiscalDocument.document_type == "return",
                *self._corrispettivi_return_order_filters(),
                return_day >= start_date,
                return_day <= end_date,
            )
            .group_by(return_day)
        )
        returns_query = self._apply_order_filters(returns_query, filters)

        result: dict = {}
        for movement_date, breakdown in sales_breakdown.items():
            result[movement_date] = {
                "sales": breakdown["net"],
                "sales_breakdown": {
                    "base": breakdown[self.SALES_COMPONENT_BASE],
                    "ricevute_decurtazione": breakdown[
                        self.SALES_COMPONENT_RICEVUTE_DECURTAZIONE
                    ],
                    "ricevute_imputazione": breakdown[
                        self.SALES_COMPONENT_RICEVUTE_IMPUTAZIONE
                    ],
                },
            }

        for row in returns_query.all():
            movement_date = self._as_date(row.movement_date)
            products_with_tax = decimal_or_zero(row.products_with_tax)
            products_net = decimal_or_zero(row.products_net)
            total_with_tax = decimal_or_zero(row.total_with_tax)
            total_net = decimal_or_zero(row.total_net)
            bucket = result.setdefault(movement_date, {})
            bucket["returns"] = {
                "total_with_tax": total_with_tax,
                "total_net": total_net,
                "products_with_tax": products_with_tax,
                "products_net": products_net,
                "shipping_with_tax": total_with_tax - products_with_tax,
                "shipping_net": total_net - products_net,
            }

        return result
