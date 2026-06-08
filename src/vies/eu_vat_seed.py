"""
Costanti e logica seed BE-VIES-1 (aliquote IVA standard UE su `taxes`).

Usato da:
- `scripts/setup_initial.py` (solo se `SEED_EU_VAT_TAXES=1`)
- migration Alembic cleanup / downgrade
- test
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable, List, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from src.models.country import Country
from src.models.tax import Tax

# Aliquote IVA standard UE (DECIMAL 5,2 — BE-ALIQ-05)
EU_VAT_STANDARD_RATES: Sequence[Tuple[str, Decimal]] = (
    ("AT", Decimal("20.00")),
    ("BE", Decimal("21.00")),
    ("BG", Decimal("20.00")),
    ("HR", Decimal("25.00")),
    ("CY", Decimal("19.00")),
    ("CZ", Decimal("21.00")),
    ("DK", Decimal("25.00")),
    ("EE", Decimal("22.00")),
    ("FI", Decimal("25.50")),
    ("FR", Decimal("20.00")),
    ("DE", Decimal("19.00")),
    ("GR", Decimal("24.00")),
    ("HU", Decimal("27.00")),
    ("IE", Decimal("23.00")),
    ("IT", Decimal("22.00")),
    ("LV", Decimal("21.00")),
    ("LT", Decimal("21.00")),
    ("LU", Decimal("17.00")),
    ("MT", Decimal("18.00")),
    ("NL", Decimal("21.00")),
    ("PL", Decimal("23.00")),
    ("PT", Decimal("23.00")),
    ("RO", Decimal("19.00")),
    ("SK", Decimal("23.00")),
    ("SI", Decimal("22.00")),
    ("ES", Decimal("21.00")),
    ("SE", Decimal("25.00")),
)

EU_ISO_CODES: frozenset[str] = frozenset(iso for iso, _ in EU_VAT_STANDARD_RATES)

SEED_NOTE_MARKER = "BE-VIES-1 seed"


def seed_note_for_country(iso_code: str) -> str:
    return f"Standard VAT {iso_code.upper()} ({SEED_NOTE_MARKER})"


def is_be_vies_1_seed_note(note: str | None) -> bool:
    if not note:
        return False
    return SEED_NOTE_MARKER in note


def _same_tax_rate(left, right) -> bool:
    return Decimal(str(left)).quantize(Decimal("0.01")) == Decimal(str(right)).quantize(
        Decimal("0.01")
    )


def seed_tax_name(iso_code: str, rate: Decimal) -> str:
    normalized = Decimal(str(rate)).normalize()
    if normalized == normalized.to_integral_value():
        rate_label = str(int(normalized))
    else:
        rate_label = format(normalized, "f").rstrip("0").rstrip(".")
    return f"IVA {iso_code.upper()} {rate_label}%"


def seed_tax_code(iso_code: str) -> str:
    return f"VAT{iso_code.upper()}"


_REFERENCED_TAX_SUBQUERIES = {
    "order_details": (
        "SELECT DISTINCT id_tax FROM order_details WHERE id_tax IS NOT NULL"
    ),
    "fiscal_document_details": (
        "SELECT DISTINCT id_tax FROM fiscal_document_details WHERE id_tax IS NOT NULL"
    ),
    "shippings": "SELECT DISTINCT id_tax FROM shippings WHERE id_tax IS NOT NULL",
}


def build_cleanup_seed_where_sql(existing_tables: Iterable[str]) -> Tuple[str, dict]:
    """
    WHERE per DELETE taxes seed BE-VIES-1 non referenziati.
    Strategy (a): skip righe referenziate.
    """
    table_set = {t.lower() for t in existing_tables}
    ref_parts = [
        sql
        for table, sql in _REFERENCED_TAX_SUBQUERIES.items()
        if table in table_set
    ]

    note_clause = (
        f"(note LIKE '%{SEED_NOTE_MARKER}%' "
        f"OR note LIKE 'Standard VAT %({SEED_NOTE_MARKER})')"
    )

    if ref_parts:
        not_in = " AND id_tax NOT IN (" + " UNION ".join(ref_parts) + ")"
    else:
        not_in = ""

    return note_clause + not_in, {}


def count_seed_taxes(connection: Connection) -> int:
    where_sql, _ = build_cleanup_seed_where_sql(_list_tables(connection))
    row = connection.execute(
        text(f"SELECT COUNT(*) FROM taxes WHERE {where_sql}")
    ).scalar()
    return int(row or 0)


def delete_be_vies_1_seed_taxes(connection: Connection) -> int:
    """Rimuove aliquote seed non referenziate. Idempotente."""
    tables = _list_tables(connection)
    where_sql, _ = build_cleanup_seed_where_sql(tables)
    result = connection.execute(text(f"DELETE FROM taxes WHERE {where_sql}"))
    return int(result.rowcount or 0)


def _list_tables(connection: Connection) -> List[str]:
    dialect = connection.dialect.name
    if dialect == "mysql":
        rows = connection.execute(text("SHOW TABLES")).fetchall()
        return [r[0] for r in rows]
    if dialect == "sqlite":
        rows = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
        return [r[0] for r in rows]
    rows = connection.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema()"
        )
    ).fetchall()
    return [r[0] for r in rows]


def setup_eu_country_taxes(db: Session) -> list:
    """
    Seed idempotente: un Tax default (is_default=1) per ogni paese UE con aliquota standard.
    Richiede righe in countries con iso_code corrispondente.
    """
    print("\n🇪🇺 Seed aliquote IVA standard UE (Tax.id_country + is_default)...")
    summary = []
    for iso_code, rate in EU_VAT_STANDARD_RATES:
        iso_upper = iso_code.upper()
        country = (
            db.query(Country)
            .filter(Country.iso_code == iso_upper)
            .first()
        )
        if not country:
            country = (
                db.query(Country)
                .filter(Country.iso_code.ilike(iso_upper))
                .first()
            )
        if not country:
            msg = f"{iso_upper}: skipped (country not in DB)"
            print(f"  ⚠️  {msg}")
            summary.append((iso_upper, rate, "skipped_no_country"))
            continue

        existing_default = (
            db.query(Tax)
            .filter(Tax.id_country == country.id_country, Tax.is_default == 1)
            .first()
        )
        matching_rate = (
            db.query(Tax)
            .filter(
                Tax.id_country == country.id_country,
                Tax.percentage == rate,
            )
            .first()
        )

        if existing_default and _same_tax_rate(existing_default.percentage, rate):
            summary.append((iso_upper, rate, "skipped"))
            print(f"  ℹ️  {iso_upper}: skipped (default già {rate}%)")
            continue

        if matching_rate and not existing_default:
            matching_rate.is_default = 1
            db.query(Tax).filter(
                Tax.id_country == country.id_country,
                Tax.id_tax != matching_rate.id_tax,
            ).update({Tax.is_default: 0}, synchronize_session=False)
            db.commit()
            summary.append((iso_upper, rate, "promoted"))
            print(
                f"  ✅ {iso_upper}: promoted existing tax id={matching_rate.id_tax} ({rate}%)"
            )
            continue

        if existing_default and not _same_tax_rate(existing_default.percentage, rate):
            existing_default.is_default = 0

        if matching_rate:
            matching_rate.is_default = 1
            db.query(Tax).filter(
                Tax.id_country == country.id_country,
                Tax.id_tax != matching_rate.id_tax,
            ).update({Tax.is_default: 0}, synchronize_session=False)
            db.commit()
            summary.append((iso_upper, rate, "promoted"))
            print(f"  ✅ {iso_upper}: promoted tax id={matching_rate.id_tax} ({rate}%)")
            continue

        new_tax = Tax(
            id_country=country.id_country,
            is_default=1,
            name=seed_tax_name(iso_upper, rate),
            note=seed_note_for_country(iso_upper),
            code=seed_tax_code(iso_upper),
            percentage=rate,
            electronic_code="",
        )
        db.add(new_tax)
        db.flush()
        db.query(Tax).filter(
            Tax.id_country == country.id_country,
            Tax.id_tax != new_tax.id_tax,
        ).update({Tax.is_default: 0}, synchronize_session=False)
        db.commit()
        summary.append((iso_upper, rate, "created"))
        print(f"  ✅ {iso_upper}: created tax id={new_tax.id_tax} ({rate}%)")

    created = sum(1 for _, _, a in summary if a == "created")
    promoted = sum(1 for _, _, a in summary if a == "promoted")
    skipped = sum(1 for _, _, a in summary if a == "skipped")
    skipped_nc = sum(1 for _, _, a in summary if a == "skipped_no_country")
    print(
        f"\n  Riepilogo seed UE: created={created}, promoted={promoted}, "
        f"skipped={skipped}, skipped_no_country={skipped_nc}"
    )
    return summary
