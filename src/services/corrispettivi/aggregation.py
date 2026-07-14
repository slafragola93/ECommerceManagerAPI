from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Tuple

from src.models.tax import Tax


@dataclass
class MovementRow:
    movement_date: date
    country_iso: Optional[str]
    id_tax: Optional[int]
    sales_net: Decimal = Decimal("0")
    returns_net: Decimal = Decimal("0")
    is_shipping: bool = False


@dataclass
class AggregateBucket:
    sales_net: Decimal = Decimal("0")
    returns_net: Decimal = Decimal("0")

    def add_sales(self, amount: Decimal) -> None:
        self.sales_net += amount

    def add_returns(self, amount: Decimal) -> None:
        self.returns_net += amount

    @property
    def net(self) -> Decimal:
        return self.sales_net - self.returns_net


def decimal_or_zero(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


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
) -> Tuple[Dict[date, Dict[int, AggregateBucket]], Dict[date, AggregateBucket]]:
    """Returns (product_buckets by date/tax, shipping_buckets by date)."""
    filtered = filter_movements(movements, country_iso)
    product_buckets: Dict[date, Dict[int, AggregateBucket]] = {}
    shipping_buckets: Dict[date, AggregateBucket] = {}

    for row in filtered:
        tax_id = row.id_tax or 0
        if row.is_shipping:
            bucket = shipping_buckets.setdefault(row.movement_date, AggregateBucket())
            if row.sales_net:
                bucket.add_sales(row.sales_net)
            if row.returns_net:
                bucket.add_returns(row.returns_net)
            continue

        day_buckets = product_buckets.setdefault(row.movement_date, {})
        bucket = day_buckets.setdefault(tax_id, AggregateBucket())
        if row.sales_net:
            bucket.add_sales(row.sales_net)
        if row.returns_net:
            bucket.add_returns(row.returns_net)

    return product_buckets, shipping_buckets


def build_riepilogo_rows(
    product_buckets: Dict[date, Dict[int, AggregateBucket]],
    shipping_buckets: Dict[date, AggregateBucket],
    taxes_by_id: Dict[int, Tax],
) -> Tuple[List[dict], List[int]]:
    all_dates = sorted(set(product_buckets.keys()) | set(shipping_buckets.keys()))
    all_tax_ids: set[int] = set()
    for day_buckets in product_buckets.values():
        all_tax_ids.update(day_buckets.keys())

    rows: List[dict] = []
    for movement_date in all_dates:
        day = movement_date.day
        day_buckets = product_buckets.get(movement_date, {})
        shipping = shipping_buckets.get(movement_date, AggregateBucket())

        cells: Dict[str, dict] = {}
        row_sales = Decimal("0")
        row_returns = Decimal("0")

        for tax_id, bucket in sorted(day_buckets.items()):
            all_tax_ids.add(tax_id)
            cells[str(tax_id)] = {
                "sales_net": bucket.sales_net,
                "returns_net": bucket.returns_net,
                "net": bucket.net,
            }
            row_sales += bucket.sales_net
            row_returns += bucket.returns_net

        row_net = {
            "sales_net": row_sales,
            "returns_net": row_returns,
            "net": row_sales - row_returns,
        }
        rows.append(
            {
                "day": day,
                "date": movement_date,
                "cells": cells,
                "row_net": row_net,
                "shipping": {
                    "sales_net": shipping.sales_net,
                    "returns_net": shipping.returns_net,
                    "net": shipping.net,
                },
            }
        )

    return rows, sorted(all_tax_ids)


def sum_amount_dict(values: Iterable[dict], key: str) -> Decimal:
    total = Decimal("0")
    for item in values:
        total += decimal_or_zero(item.get(key))
    return total


def build_month_totals(rows: List[dict]) -> dict:
    row_nets = [row["row_net"] for row in rows]
    return {
        "sales_net": sum_amount_dict(row_nets, "sales_net"),
        "returns_net": sum_amount_dict(row_nets, "returns_net"),
        "net": sum_amount_dict(row_nets, "net"),
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
                "sales_with_tax": Decimal("0"),
                "sales_net": Decimal("0"),
                "sales_products_with_tax": Decimal("0"),
                "sales_products_net": Decimal("0"),
                "sales_shipping_with_tax": Decimal("0"),
                "sales_shipping_net": Decimal("0"),
                "sales_order_ids": set(),
                "returns_with_tax": Decimal("0"),
                "returns_net": Decimal("0"),
                "returns_products_with_tax": Decimal("0"),
                "returns_products_net": Decimal("0"),
                "returns_shipping_with_tax": Decimal("0"),
                "returns_shipping_net": Decimal("0"),
                "returns_doc_ids": set(),
            },
        )

    for row in filtered:
        bucket = ensure_day(row.movement_date)
        if row.is_shipping:
            if row.sales_net:
                bucket["sales_shipping_net"] += row.sales_net
            if row.returns_net:
                bucket["returns_shipping_net"] += row.returns_net
            continue

        if row.sales_net:
            bucket["sales_net"] += row.sales_net
            bucket["sales_products_net"] += row.sales_net
        if row.returns_net:
            bucket["returns_net"] += row.returns_net
            bucket["returns_products_net"] += row.returns_net

    summaries = []
    for movement_date in sorted(days.keys()):
        bucket = days[movement_date]
        sales_net = bucket["sales_net"] + bucket["sales_shipping_net"]
        sales_products_net = bucket["sales_products_net"]
        sales_shipping_net = bucket["sales_shipping_net"]
        returns_net = bucket["returns_net"] + bucket["returns_shipping_net"]
        returns_products_net = bucket["returns_products_net"]
        returns_shipping_net = bucket["returns_shipping_net"]

        def with_tax_from_net(net: Decimal) -> Decimal:
            return net

        summaries.append(
            {
                "date": movement_date,
                "sales": {
                    "total_with_tax": sales_net,
                    "total_net": sales_net,
                    "products_with_tax": sales_products_net,
                    "products_net": sales_products_net,
                    "shipping_with_tax": sales_shipping_net,
                    "shipping_net": sales_shipping_net,
                    "order_count": len(bucket["sales_order_ids"]),
                },
                "returns": {
                    "total_with_tax": returns_net,
                    "total_net": returns_net,
                    "products_with_tax": returns_products_net,
                    "products_net": returns_products_net,
                    "shipping_with_tax": returns_shipping_net,
                    "shipping_net": returns_shipping_net,
                    "return_count": len(bucket["returns_doc_ids"]),
                },
                "net": {
                    "total_with_tax": sales_net - returns_net,
                    "total_net": sales_net - returns_net,
                    "products_with_tax": sales_products_net - returns_products_net,
                    "products_net": sales_products_net - returns_products_net,
                    "shipping_with_tax": sales_shipping_net - returns_shipping_net,
                    "shipping_net": sales_shipping_net - returns_shipping_net,
                    "order_count": 0,
                    "return_count": 0,
                },
            }
        )

    return summaries
