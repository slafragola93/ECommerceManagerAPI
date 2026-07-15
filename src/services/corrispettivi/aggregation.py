from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, Iterable, List, Optional

from src.models.tax import Tax


@dataclass
class MovementRow:
    movement_date: date
    country_iso: Optional[str]
    id_tax: Optional[int]
    sales_amount: Decimal = Decimal("0")
    returns_amount: Decimal = Decimal("0")
    is_shipping: bool = False


@dataclass
class TaxBucket:
    products_sales: Decimal = Decimal("0")
    shipping_sales: Decimal = Decimal("0")
    products_returns: Decimal = Decimal("0")
    shipping_returns: Decimal = Decimal("0")

    def add_products_sales(self, amount: Decimal) -> None:
        self.products_sales += amount

    def add_shipping_sales(self, amount: Decimal) -> None:
        self.shipping_sales += amount

    def add_products_returns(self, amount: Decimal) -> None:
        self.products_returns += amount

    def add_shipping_returns(self, amount: Decimal) -> None:
        self.shipping_returns += amount

    @property
    def balance(self) -> Decimal:
        return (
            self.products_sales
            + self.shipping_sales
            - self.products_returns
            - self.shipping_returns
        )

    def to_dict(self) -> dict:
        return {
            "products_sales": self.products_sales,
            "shipping_sales": self.shipping_sales,
            "products_returns": self.products_returns,
            "shipping_returns": self.shipping_returns,
        }


def decimal_or_zero(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def iter_month_dates(
    year: int, month: int, day: Optional[int] = None
) -> List[date]:
    if day is not None:
        return [date(year, month, day)]
    last_day = calendar.monthrange(year, month)[1]
    return [date(year, month, current_day) for current_day in range(1, last_day + 1)]


def tax_column_label(tax: Tax) -> str:
    if tax.code and str(tax.code).strip():
        return str(tax.code).strip()
    if tax.electronic_code and str(tax.electronic_code).strip():
        return str(tax.electronic_code).strip()
    pct = float(tax.percentage)
    if pct == int(pct):
        return str(int(pct))
    return str(pct)


def build_tax_columns(tax_ids: Iterable[int], taxes_by_id: Dict[int, Tax]) -> List[dict]:
    columns = []
    for tax_id in sorted(set(tax_ids)):
        tax = taxes_by_id.get(tax_id)
        if not tax:
            columns.append(
                {
                    "id_tax": tax_id,
                    "label": str(tax_id),
                    "percentage": None,
                }
            )
            continue
        columns.append(
            {
                "id_tax": tax_id,
                "label": tax_column_label(tax),
                "percentage": float(tax.percentage) if tax.percentage is not None else None,
            }
        )
    return columns


def filter_movements(
    movements: Iterable[MovementRow],
    country_iso: Optional[str] = None,
) -> List[MovementRow]:
    rows = list(movements)
    if not country_iso:
        return rows
    normalized = country_iso.upper()
    return [row for row in rows if (row.country_iso or "").upper() == normalized]


def aggregate_matrix(
    movements: Iterable[MovementRow],
    country_iso: Optional[str] = None,
) -> Dict[date, Dict[int, TaxBucket]]:
    """Returns tax buckets by date and aliquota (products + shipping per id_tax)."""
    filtered = filter_movements(movements, country_iso)
    matrix: Dict[date, Dict[int, TaxBucket]] = {}

    for row in filtered:
        tax_id = row.id_tax or 0
        day_buckets = matrix.setdefault(row.movement_date, {})
        bucket = day_buckets.setdefault(tax_id, TaxBucket())
        if row.is_shipping:
            if row.sales_amount:
                bucket.add_shipping_sales(row.sales_amount)
            if row.returns_amount:
                bucket.add_shipping_returns(row.returns_amount)
            continue

        if row.sales_amount:
            bucket.add_products_sales(row.sales_amount)
        if row.returns_amount:
            bucket.add_products_returns(row.returns_amount)

    return matrix


def build_riepilogo_rows(
    matrix: Dict[date, Dict[int, TaxBucket]],
    year: int,
    month: int,
    taxes_by_id: Dict[int, Tax],
    day: Optional[int] = None,
) -> tuple[List[dict], List[int]]:
    all_tax_ids: set[int] = set()
    for day_buckets in matrix.values():
        all_tax_ids.update(day_buckets.keys())

    tax_ids = sorted(all_tax_ids)
    rows: List[dict] = []

    for movement_date in iter_month_dates(year, month, day):
        day_buckets = matrix.get(movement_date, {})
        cells: Dict[str, dict] = {}
        row_total = Decimal("0")

        for tax_id in tax_ids:
            bucket = day_buckets.get(tax_id, TaxBucket())
            cells[str(tax_id)] = bucket.to_dict()
            row_total += bucket.balance

        rows.append(
            {
                "day": movement_date.day,
                "date": movement_date,
                "cells": cells,
                "row_total": row_total,
            }
        )

    return rows, tax_ids


def build_month_totals(rows: List[dict]) -> dict:
    totals = TaxBucket()
    row_total = Decimal("0")

    for row in rows:
        row_total += decimal_or_zero(row.get("row_total"))
        for cell in row.get("cells", {}).values():
            totals.products_sales += decimal_or_zero(cell.get("products_sales"))
            totals.shipping_sales += decimal_or_zero(cell.get("shipping_sales"))
            totals.products_returns += decimal_or_zero(cell.get("products_returns"))
            totals.shipping_returns += decimal_or_zero(cell.get("shipping_returns"))

    return {
        **totals.to_dict(),
        "row_total": row_total,
    }


def build_daily_summaries(
    movements: Iterable[MovementRow],
    country_iso: Optional[str] = None,
) -> List[dict]:
    filtered = filter_movements(movements, country_iso)
    days: Dict[date, dict] = {}

    def ensure_day(movement_date: date) -> dict:
        return days.setdefault(
            movement_date,
            {
                "sales_products_with_tax": Decimal("0"),
                "sales_shipping_with_tax": Decimal("0"),
                "returns_products_with_tax": Decimal("0"),
                "returns_shipping_with_tax": Decimal("0"),
                "sales_order_ids": set(),
                "returns_doc_ids": set(),
            },
        )

    for row in filtered:
        bucket = ensure_day(row.movement_date)
        if row.is_shipping:
            if row.sales_amount:
                bucket["sales_shipping_with_tax"] += row.sales_amount
            if row.returns_amount:
                bucket["returns_shipping_with_tax"] += row.returns_amount
            continue

        if row.sales_amount:
            bucket["sales_products_with_tax"] += row.sales_amount
        if row.returns_amount:
            bucket["returns_products_with_tax"] += row.returns_amount

    summaries = []
    for movement_date in sorted(days.keys()):
        bucket = days[movement_date]
        sales_products = bucket["sales_products_with_tax"]
        sales_shipping = bucket["sales_shipping_with_tax"]
        returns_products = bucket["returns_products_with_tax"]
        returns_shipping = bucket["returns_shipping_with_tax"]
        sales_total = sales_products + sales_shipping
        returns_total = returns_products + returns_shipping

        summaries.append(
            {
                "date": movement_date,
                "sales": {
                    "total_with_tax": sales_total,
                    "total_net": sales_total,
                    "products_with_tax": sales_products,
                    "products_net": sales_products,
                    "shipping_with_tax": sales_shipping,
                    "shipping_net": sales_shipping,
                    "order_count": len(bucket["sales_order_ids"]),
                },
                "returns": {
                    "total_with_tax": returns_total,
                    "total_net": returns_total,
                    "products_with_tax": returns_products,
                    "products_net": returns_products,
                    "shipping_with_tax": returns_shipping,
                    "shipping_net": returns_shipping,
                    "return_count": len(bucket["returns_doc_ids"]),
                },
                "net": {
                    "total_with_tax": sales_total - returns_total,
                    "total_net": sales_total - returns_total,
                    "products_with_tax": sales_products - returns_products,
                    "products_net": sales_products - returns_products,
                    "shipping_with_tax": sales_shipping - returns_shipping,
                    "shipping_net": sales_shipping - returns_shipping,
                    "order_count": 0,
                    "return_count": 0,
                },
            }
        )

    return summaries
