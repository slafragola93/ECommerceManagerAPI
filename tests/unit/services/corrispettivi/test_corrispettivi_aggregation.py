from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from src.services.corrispettivi.aggregation import (
    MovementRow,
    TaxBucket,
    aggregate_matrix,
    build_month_totals,
    build_riepilogo_rows,
    build_tax_columns,
    iter_month_dates,
    tax_column_label,
)
from src.services.export.corrispettivi_excel_service import CorrispettiviExcelService
from src.schemas.corrispettivo_schema import (
    CorrispettivoRiepilogoResponseSchema,
    CorrispettivoRiepilogoRowSchema,
    CorrispettivoRiepilogoTotalsSchema,
    CorrispettivoTaxCellSchema,
    CorrispettivoTaxColumnSchema,
)
import zipfile
import io


def test_tax_column_label_prefers_code():
    tax = SimpleNamespace(code="SPF", electronic_code="N3.4", percentage=Decimal("22.00"))
    assert tax_column_label(tax) == "SPF"


def test_tax_column_label_uses_percentage_when_no_code():
    tax = SimpleNamespace(code="", electronic_code="", percentage=Decimal("22.00"))
    assert tax_column_label(tax) == "22"


def test_iter_month_dates_includes_full_month():
    dates = iter_month_dates(2026, 2)
    assert len(dates) == 28
    assert dates[0] == date(2026, 2, 1)
    assert dates[-1] == date(2026, 2, 28)


def test_aggregate_matrix_splits_country_and_shipping_per_tax():
    day = date(2026, 5, 15)
    movements = [
        MovementRow(day, "IT", 1, sales_amount=Decimal("100.00")),
        MovementRow(day, "DE", 1, sales_amount=Decimal("50.00")),
        MovementRow(day, "IT", 2, sales_amount=Decimal("10.00"), is_shipping=True),
        MovementRow(day, "IT", 1, returns_amount=Decimal("20.00")),
    ]

    matrix = aggregate_matrix(movements, country_iso="IT")
    assert matrix[day][1].products_sales == Decimal("100.00")
    assert matrix[day][1].products_returns == Decimal("20.00")
    assert matrix[day][2].shipping_sales == Decimal("10.00")


def test_build_riepilogo_rows_and_month_totals():
    day = date(2026, 5, 15)
    matrix = {
        day: {
            1: TaxBucket(
                products_sales=Decimal("100.00"),
                products_returns=Decimal("10.00"),
                shipping_sales=Decimal("5.00"),
                shipping_returns=Decimal("2.00"),
            )
        }
    }
    taxes_by_id = {
        1: SimpleNamespace(code="22", electronic_code="", percentage=Decimal("22.00")),
    }

    rows, tax_ids = build_riepilogo_rows(matrix, 2026, 5, taxes_by_id)
    assert len(rows) == 31
    row = next(item for item in rows if item["date"] == day)
    assert row["row_total"] == Decimal("93.00")
    assert row["cells"]["1"]["shipping_returns"] == Decimal("2.00")
    assert tax_ids == [1]

    columns = build_tax_columns(tax_ids, taxes_by_id)
    assert columns[0]["label"] == "22"

    totals = build_month_totals(rows)
    assert totals["row_total"] == Decimal("93.00")


def test_build_registri_zip_contains_expected_files():
    riepilogo = CorrispettivoRiepilogoResponseSchema(
        year=2026,
        month=5,
        columns=[CorrispettivoTaxColumnSchema(id_tax=1, label="22", percentage=22.0)],
        rows=[
            CorrispettivoRiepilogoRowSchema(
                day=15,
                date=date(2026, 5, 15),
                cells={
                    "1": CorrispettivoTaxCellSchema(
                        products_sales=Decimal("122.00"),
                        products_returns=Decimal("12.20"),
                    )
                },
                row_total=Decimal("109.80"),
            )
        ],
        month_totals=CorrispettivoRiepilogoTotalsSchema(
            products_sales=Decimal("122.00"),
            products_returns=Decimal("12.20"),
            row_total=Decimal("109.80"),
        ),
    )

    zip_bytes = CorrispettiviExcelService().build_registri_zip(
        consolidated_riepilogo=riepilogo,
        by_country={"IT": riepilogo, "DE": riepilogo},
    )

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = set(archive.namelist())
    assert "registro.xlsx" in names
    assert "registro_IT.xlsx" in names
    assert "registro_DE.xlsx" in names


def test_export_filters_without_country_strips_delivery_iso():
    from src.schemas.corrispettivo_schema import CorrispettivoFiltersSchema
    from src.services.routers.corrispettivo_service import CorrispettivoService

    filters = CorrispettivoFiltersSchema(id_store=1, delivery_country_iso="FR")
    result = CorrispettivoService._filters_without_country(filters)

    assert result is not None
    assert result.id_store == 1
    assert result.delivery_country_iso is None
