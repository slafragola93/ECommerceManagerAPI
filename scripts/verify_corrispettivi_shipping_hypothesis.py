"""Verifica ipotesi su check A/B del report ZIP corrispettivi giugno 2026.

Ipotesi:
  1. Check A (prodotti>0, spedizione=0 per aliquota): spedizione in altra colonna aliquota
     oppure spedizione gratuita a livello giorno.
  2. Check B (spedizione>0, prodotti=0 per aliquota): prodotti in altra colonna aliquota.

Uso:
  python scripts/verify_corrispettivi_shipping_hypothesis.py
  python scripts/verify_corrispettivi_shipping_hypothesis.py --year 2026 --month 6
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal

from dotenv import load_dotenv
from sqlalchemy import exists, func, or_, select

load_dotenv()

from src.database import SessionLocal  # noqa: E402
from src.models.fiscal_document import FiscalDocument  # noqa: E402
from src.models.order import Order  # noqa: E402
from src.models.order_detail import OrderDetail  # noqa: E402
from src.models.ricevuta import Ricevuta, RicevutaStato  # noqa: E402
from src.models.shipping import Shipping  # noqa: E402
from src.models.tax import Tax  # noqa: E402
from src.repository.corrispettivo_repository import CorrispettivoRepository  # noqa: E402
from src.services.corrispettivi.aggregation import (  # noqa: E402
    aggregate_matrix,
    build_riepilogo_rows,
    tax_column_label,
)

# Casi segnalati nel report CORRISPETTIVI_ZIP_VALIDAZIONE_GIUGNO_2026.md
REPORT_CHECK_A = [
    ("2026-06-01", "SM", Decimal("1809.99")),
    ("2026-06-01", "22", Decimal("11.72")),
    ("2026-06-01", "N3.2", Decimal("2737.97")),
    ("2026-06-04", "N3.2", Decimal("31.36")),
    ("2026-06-05", "N3.2", Decimal("306.6")),
    ("2026-06-08", "N3.2", Decimal("551.67")),
    ("2026-06-10", "20", Decimal("2743.5")),
    ("2026-06-12", "N3.2", Decimal("296.61")),
    ("2026-06-15", "25.5", Decimal("289.97")),
    ("2026-06-16", "N3.2", Decimal("7.07")),
    ("2026-06-23", "22", Decimal("3463.95")),
    ("2026-06-23", "20", Decimal("2752.06")),
    ("2026-06-23", "N3.2", Decimal("9505.32")),
    ("2026-06-29", "22", Decimal("3134.24")),
    ("2026-06-29", "N3.2", Decimal("2318.58")),
    ("2026-06-30", "22", Decimal("11.92")),
]

REPORT_CHECK_B = [
    ("2026-06-01", "20", Decimal("12")),
    ("2026-06-01", "22.", Decimal("96.37")),
    ("2026-06-04", "20", Decimal("12")),
    ("2026-06-05", "20", Decimal("12")),
    ("2026-06-08", "20", Decimal("74.99")),
    ("2026-06-10", "22", Decimal("66167.32")),
    ("2026-06-12", "20", Decimal("50.99")),
    ("2026-06-16", "20", Decimal("18.98")),
    ("2026-06-23", "22", Decimal("48.8")),
    ("2026-06-30", "N3.2", Decimal("8.33")),
]


def _normalize_label(label: str) -> str:
    return label.strip().rstrip(".")


def _load_taxes(session) -> dict[int, Tax]:
    return {tax.id_tax: tax for tax in session.query(Tax).all()}


def _label_to_tax_ids(taxes_by_id: dict[int, Tax]) -> dict[str, list[int]]:
    mapping: dict[str, list[int]] = defaultdict(list)
    for tax_id, tax in taxes_by_id.items():
        mapping[_normalize_label(tax_column_label(tax))].append(tax_id)
    return mapping


def _find_cell(
    rows_by_date: dict[date, dict],
    tax_ids: list[int],
    movement_date: date,
) -> dict:
    row = rows_by_date.get(movement_date, {})
    cells = row.get("cells", {})
    merged = {
        "products_sales": Decimal("0"),
        "shipping_sales": Decimal("0"),
        "products_returns": Decimal("0"),
        "shipping_returns": Decimal("0"),
    }
    for tax_id in tax_ids:
        cell = cells.get(str(tax_id), {})
        for key in merged:
            merged[key] += Decimal(str(cell.get(key, 0)))
    return merged


def _day_totals(rows_by_date: dict[date, dict], movement_date: date) -> dict:
    row = rows_by_date.get(movement_date, {})
    totals = {
        "products_sales": Decimal("0"),
        "shipping_sales": Decimal("0"),
    }
    for cell in row.get("cells", {}).values():
        totals["products_sales"] += Decimal(str(cell.get("products_sales", 0)))
        totals["shipping_sales"] += Decimal(str(cell.get("shipping_sales", 0)))
    return totals


def _analyze_export_matrix(session, year: int, month: int):
    repo = CorrispettivoRepository(session)
    taxes_by_id = _load_taxes(session)
    label_map = _label_to_tax_ids(taxes_by_id)

    movements = repo.fetch_movements(year, month, filters=None)
    matrix = aggregate_matrix(movements)
    rows, tax_ids = build_riepilogo_rows(matrix, year, month, taxes_by_id)
    rows_by_date = {row["date"]: row for row in rows}

    print(f"\n=== Matrice export (movimenti={len(movements)}, aliquote={len(tax_ids)}) ===")

    def explain_check_a(day_str: str, label: str, expected_products: Decimal):
        movement_date = date.fromisoformat(day_str)
        tax_ids_for_label = label_map.get(_normalize_label(label), [])
        cell = _find_cell(rows_by_date, tax_ids_for_label, movement_date)
        day = _day_totals(rows_by_date, movement_date)

        other_shipping = Decimal("0")
        other_products = Decimal("0")
        row = rows_by_date.get(movement_date, {})
        for tid_str, c in row.get("cells", {}).items():
            if int(tid_str) in tax_ids_for_label:
                continue
            other_shipping += Decimal(str(c.get("shipping_sales", 0)))
            other_products += Decimal(str(c.get("products_sales", 0)))

        if cell["products_sales"] == 0 and expected_products > 0:
            status = "DATI_ASSENTI"
        elif cell["products_sales"] > 0 and cell["shipping_sales"] == 0:
            if other_shipping > 0:
                status = "SPIEGATO_ALIQUOTA_DIVERSA"
            elif day["shipping_sales"] == 0:
                status = "SPIEGATO_SPEDIZIONE_GRATUITA"
            else:
                status = "NON_SPIEGATO"
        else:
            status = "NON_PIU_FLAG"

        print(
            f"  A {day_str} {label:6} prod={cell['products_sales']:>12} ship={cell['shipping_sales']:>10} "
            f"| altre ship={other_shipping:>10} altre prod={other_products:>12} "
            f"| giorno ship={day['shipping_sales']:>10} -> {status}"
        )
        return status

    def explain_check_b(day_str: str, label: str, expected_shipping: Decimal):
        movement_date = date.fromisoformat(day_str)
        tax_ids_for_label = label_map.get(_normalize_label(label), [])
        cell = _find_cell(rows_by_date, tax_ids_for_label, movement_date)
        day = _day_totals(rows_by_date, movement_date)

        other_shipping = Decimal("0")
        other_products = Decimal("0")
        row = rows_by_date.get(movement_date, {})
        for tid_str, c in row.get("cells", {}).items():
            if int(tid_str) in tax_ids_for_label:
                continue
            other_shipping += Decimal(str(c.get("shipping_sales", 0)))
            other_products += Decimal(str(c.get("products_sales", 0)))

        if cell["shipping_sales"] == 0 and expected_shipping > 0:
            status = "DATI_ASSENTI"
        elif cell["shipping_sales"] > 0 and cell["products_sales"] == 0:
            if other_products > 0:
                status = "SPIEGATO_ALIQUOTA_DIVERSA"
            else:
                status = "SOLO_SPEDIZIONE"
        else:
            status = "NON_PIU_FLAG"

        print(
            f"  B {day_str} {label:6} prod={cell['products_sales']:>12} ship={cell['shipping_sales']:>10} "
            f"| altre ship={other_shipping:>10} altre prod={other_products:>12} "
            f"| giorno prod={day['products_sales']:>12} -> {status}"
        )
        return status

    print("\n--- Check A (report) ---")
    a_stats: dict[str, int] = defaultdict(int)
    for case in REPORT_CHECK_A:
        a_stats[explain_check_a(*case)] += 1

    print("\n--- Check B (report) ---")
    b_stats: dict[str, int] = defaultdict(int)
    for case in REPORT_CHECK_B:
        b_stats[explain_check_b(*case)] += 1

    print("\n--- Riepilogo check A ---")
    for key, count in sorted(a_stats.items()):
        print(f"  {key}: {count}")

    print("\n--- Riepilogo check B ---")
    for key, count in sorted(b_stats.items()):
        print(f"  {key}: {count}")

    print("\n--- Validazione per giorno (regola corretta) ---")
    day_flags = 0
    for row in rows:
        day = _day_totals(rows_by_date, row["date"])
        if day["products_sales"] > 0 and day["shipping_sales"] == 0:
            day_flags += 1
            print(
                f"  {row['date']} prod={day['products_sales']:>12} ship=0 "
                f"(possibile spedizione gratuita su tutti gli ordini del giorno)"
            )
    if day_flags == 0:
        print("  Nessun giorno con prodotti>0 e spedizione totale=0")

    return a_stats, b_stats, day_flags


def _order_level_analysis(session, year: int, month: int):
    repo = CorrispettivoRepository(session)
    order_day = repo._local_day_expr(Order.date_add)

    no_invoice = ~exists(
        select(FiscalDocument.id_fiscal_document).where(
            FiscalDocument.id_order == Order.id_order,
            FiscalDocument.document_type == "invoice",
        )
    ).correlate(Order)

    deferred_ricevuta = exists(
        select(Ricevuta.id_ricevuta).where(
            Ricevuta.id_order == Order.id_order,
            Ricevuta.stato == RicevutaStato.EMESSA,
            func.date(Ricevuta.data_emissione) != func.date(Order.date_add),
        )
    ).correlate(Order)

    start = date(year, month, 1)
    end = date(year, month, 30 if month == 6 else 28)

    flagged_dates = sorted({date.fromisoformat(d) for d, _, _ in REPORT_CHECK_A + REPORT_CHECK_B})

    print("\n=== Analisi ordini (date segnalate nel report) ===")

    for movement_date in flagged_dates:
        orders = (
            session.query(Order)
            .outerjoin(Shipping, Order.id_shipping == Shipping.id_shipping)
            .filter(
                no_invoice,
                Order.is_payed.is_(True),
                ~deferred_ricevuta,
                order_day == movement_date,
            )
            .all()
        )

        free_shipping = 0
        paid_shipping = 0
        tax_mismatch = 0
        same_tax_only = 0
        shipping_only_tax = 0

        mismatch_amount = Decimal("0")

        for order in orders:
            shipping = order.shipments if hasattr(order, "shipments") else None
            ship_row = (
                session.query(Shipping)
                .filter(Shipping.id_shipping == order.id_shipping)
                .first()
            )
            ship_amount = Decimal(str(ship_row.price_tax_incl or 0)) if ship_row else Decimal("0")
            ship_tax = ship_row.id_tax if ship_row else None

            product_rows = (
                session.query(OrderDetail.id_tax, func.sum(OrderDetail.total_price_with_tax))
                .filter(OrderDetail.id_order == order.id_order)
                .group_by(OrderDetail.id_tax)
                .all()
            )
            product_tax_ids = {row[0] for row in product_rows if Decimal(str(row[1] or 0)) > 0}

            if ship_amount <= 0:
                free_shipping += 1
                continue

            paid_shipping += 1
            if not product_tax_ids:
                shipping_only_tax += 1
                continue

            if ship_tax not in product_tax_ids:
                tax_mismatch += 1
                mismatch_amount += ship_amount
            else:
                same_tax_only += 1

        print(
            f"\n  {movement_date}: ordini={len(orders)} "
            f"| sped.gratis={free_shipping} sped.pagata={paid_shipping} "
            f"| mismatch aliquota={tax_mismatch} stessa aliquota={same_tax_only} "
            f"solo spedizione={shipping_only_tax}"
        )
        if tax_mismatch:
            print(f"    importo spedizione con aliquota != prodotti: {mismatch_amount:.2f}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--month", type=int, default=6)
    args = parser.parse_args()

    session = SessionLocal()
    try:
        _analyze_export_matrix(session, args.year, args.month)
        _order_level_analysis(session, args.year, args.month)
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
