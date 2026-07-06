from __future__ import annotations

import calendar
from datetime import date
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from src.models.address import Address
from src.models.country import Country
from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.shipping import Shipping
from src.models.tax import Tax
from src.services.corrispettivi.aggregation import MovementRow, decimal_or_zero


class CorrispettivoRepository:
    TIMEZONE = "Europe/Rome"

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

    def _period_bounds(self, year: int, month: int, day: Optional[int] = None) -> tuple[date, date]:
        if day is not None:
            start = date(year, month, day)
            return start, start
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)

    def _local_day_expr(self, column):
        converted = func.convert_tz(column, "+00:00", self.TIMEZONE)
        return func.coalesce(func.date(converted), func.date(column))

    def _apply_order_filters(self, query, filters: Optional[dict]):
        if not filters:
            return query
        if filters.get("id_platform"):
            query = query.filter(Order.id_platform == filters["id_platform"])
        if filters.get("id_store"):
            query = query.filter(Order.id_store == filters["id_store"])
        if filters.get("delivery_country_iso"):
            query = query.filter(
                func.upper(Country.iso_code) == filters["delivery_country_iso"].upper()
            )
        return query

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
                self._no_invoice_filter(),
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
                    movement_date=row.movement_date,
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
                self._no_invoice_filter(),
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
                    movement_date=row.movement_date,
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
                self._no_invoice_filter(),
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
                    movement_date=row.movement_date,
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
                self._no_invoice_filter(),
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
                    movement_date=movement_date,
                    country_iso=country_iso,
                    id_tax=shipping_tax_id,
                    returns_net=shipping_net,
                    is_shipping=True,
                )
            )

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
                self._no_invoice_filter(),
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
                self._no_invoice_filter(),
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
            counts[row.movement_date] = (int(row.order_count or 0), counts.get(row.movement_date, (0, 0))[1])
        for row in returns_query.all():
            existing = counts.get(row.movement_date, (0, 0))
            counts[row.movement_date] = (existing[0], int(row.return_count or 0))
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
        order_day = self._local_day_expr(Order.date_add)
        return_day = self._local_day_expr(FiscalDocument.date_add)

        sales_query = (
            self._session.query(
                order_day.label("movement_date"),
                func.sum(Order.total_price_with_tax).label("total_with_tax"),
                func.sum(Order.total_price_net).label("total_net"),
                func.sum(Order.products_total_price_with_tax).label("products_with_tax"),
                func.sum(Order.products_total_price_net).label("products_net"),
            )
            .select_from(Order)
            .filter(
                self._no_invoice_filter(),
                order_day >= start_date,
                order_day <= end_date,
            )
            .group_by(order_day)
        )
        sales_query = self._apply_order_filters(sales_query, filters)

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
                self._no_invoice_filter(),
                return_day >= start_date,
                return_day <= end_date,
            )
            .group_by(return_day)
        )
        returns_query = self._apply_order_filters(returns_query, filters)

        result: dict = {}
        for row in sales_query.all():
            products_with_tax = decimal_or_zero(row.products_with_tax)
            products_net = decimal_or_zero(row.products_net)
            total_with_tax = decimal_or_zero(row.total_with_tax)
            total_net = decimal_or_zero(row.total_net)
            result[row.movement_date] = {
                "sales": {
                    "total_with_tax": total_with_tax,
                    "total_net": total_net,
                    "products_with_tax": products_with_tax,
                    "products_net": products_net,
                    "shipping_with_tax": total_with_tax - products_with_tax,
                    "shipping_net": total_net - products_net,
                }
            }

        for row in returns_query.all():
            products_with_tax = decimal_or_zero(row.products_with_tax)
            products_net = decimal_or_zero(row.products_net)
            total_with_tax = decimal_or_zero(row.total_with_tax)
            total_net = decimal_or_zero(row.total_net)
            bucket = result.setdefault(row.movement_date, {})
            bucket["returns"] = {
                "total_with_tax": total_with_tax,
                "total_net": total_net,
                "products_with_tax": products_with_tax,
                "products_net": products_net,
                "shipping_with_tax": total_with_tax - products_with_tax,
                "shipping_net": total_net - products_net,
            }

        return result
