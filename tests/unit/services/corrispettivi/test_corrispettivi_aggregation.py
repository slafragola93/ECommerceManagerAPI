from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from src.services.corrispettivi.aggregation import (
    AggregateBucket,
    MovementRow,
    aggregate_matrix,
    build_month_totals,
    build_riepilogo_rows,
    build_tax_columns,
    tax_column_label,
)
from src.services.export.corrispettivi_excel_service import CorrispettiviExcelService
from src.schemas.corrispettivo_schema import (
    CorrispettivoAmountSchema,
    CorrispettivoRiepilogoResponseSchema,
    CorrispettivoRiepilogoRowSchema,
    CorrispettivoShippingDaySchema,
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


def test_aggregate_matrix_splits_country_and_shipping():
    day = date(2026, 5, 15)
    movements = [
        MovementRow(day, "IT", 1, sales_net=Decimal("100.00")),
        MovementRow(day, "DE", 1, sales_net=Decimal("50.00")),
        MovementRow(day, "IT", 2, sales_net=Decimal("10.00"), is_shipping=True),
        MovementRow(day, "IT", 1, returns_net=Decimal("20.00")),
    ]

    product_buckets, shipping_buckets = aggregate_matrix(movements, country_iso="IT")
    assert product_buckets[day][1].sales_net == Decimal("100.00")
    assert product_buckets[day][1].returns_net == Decimal("20.00")
    assert 1 not in product_buckets[day] or product_buckets[day].get(1).sales_net == Decimal("100.00")
    assert shipping_buckets[day].sales_net == Decimal("10.00")


def test_build_riepilogo_rows_and_month_totals():
    day = date(2026, 5, 15)
    product_buckets = {
        day: {
            1: AggregateBucket(
                sales_net=Decimal("100.00"),
                returns_net=Decimal("10.00"),
            )
        }
    }
    shipping_buckets = {
        day: AggregateBucket(
            sales_net=Decimal("5.00"),
            returns_net=Decimal("2.00"),
        )
    }
    taxes_by_id = {
        1: SimpleNamespace(code="22", electronic_code="", percentage=Decimal("22.00")),
    }

    rows, tax_ids = build_riepilogo_rows(product_buckets, shipping_buckets, taxes_by_id)
    assert len(rows) == 1
    assert rows[0]["row_net"]["net"] == Decimal("90.00")
    assert rows[0]["shipping"]["returns_net"] == Decimal("2.00")
    assert rows[0]["shipping"]["net"] == Decimal("3.00")
    assert tax_ids == [1]

    columns = build_tax_columns(tax_ids, taxes_by_id)
    assert columns[0]["label"] == "22"

    totals = build_month_totals(rows)
    assert totals["net"] == Decimal("90.00")


def test_build_registri_zip_contains_expected_files():
    from src.schemas.corrispettivo_schema import (
        CorrispettivoDaySummarySchema,
        CorrispettivoListResponseSchema,
        CorrispettivoSplitTotalsSchema,
    )

    day_summary = CorrispettivoDaySummarySchema(
        date=date(2026, 5, 15),
        sales=CorrispettivoSplitTotalsSchema(
            total_with_tax=Decimal("122.00"),
            products_with_tax=Decimal("122.00"),
            shipping_with_tax=Decimal("0.00"),
        ),
        returns=CorrispettivoSplitTotalsSchema(
            total_with_tax=Decimal("12.20"),
            products_with_tax=Decimal("12.20"),
        ),
        net=CorrispettivoSplitTotalsSchema(
            total_with_tax=Decimal("109.80"),
            products_with_tax=Decimal("109.80"),
            shipping_with_tax=Decimal("0.00"),
        ),
    )
    summary = CorrispettivoListResponseSchema(
        year=2026,
        month=5,
        days=[day_summary],
        month_totals=day_summary.net,
    )

    zip_bytes = CorrispettiviExcelService().build_registri_zip(
        consolidated_riepilogo=CorrispettivoRiepilogoResponseSchema(
            year=2026,
            month=5,
            columns=[CorrispettivoTaxColumnSchema(id_tax=1, label="22", percentage=22.0)],
            rows=[
                CorrispettivoRiepilogoRowSchema(
                    day=15,
                    date=date(2026, 5, 15),
                    cells={
                        "1": CorrispettivoAmountSchema(
                            sales_net=Decimal("109.80"),
                            returns_net=Decimal("12.20"),
                            net=Decimal("97.60"),
                        )
                    },
                    row_net=CorrispettivoAmountSchema(
                        sales_net=Decimal("109.80"),
                        returns_net=Decimal("12.20"),
                        net=Decimal("97.60"),
                    ),
                    shipping=CorrispettivoShippingDaySchema(),
                )
            ],
            month_totals=CorrispettivoAmountSchema(
                sales_net=Decimal("109.80"),
                returns_net=Decimal("12.20"),
                net=Decimal("97.60"),
            ),
        ),
        by_country={"IT": summary, "DE": summary},
    )

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = set(archive.namelist())
        assert "registro.xlsx" in names
        assert "registro_IT.xlsx" in names
        assert "registro_DE.xlsx" in names


def test_build_workbook_has_simplified_with_tax_columns():
    from openpyxl import load_workbook

    from src.schemas.corrispettivo_schema import (
        CorrispettivoDaySummarySchema,
        CorrispettivoListResponseSchema,
        CorrispettivoSplitTotalsSchema,
    )

    day = CorrispettivoDaySummarySchema(
        date=date(2026, 5, 15),
        sales=CorrispettivoSplitTotalsSchema(
            total_with_tax=Decimal("122.00"),
            products_with_tax=Decimal("100.00"),
            shipping_with_tax=Decimal("22.00"),
        ),
        returns=CorrispettivoSplitTotalsSchema(
            total_with_tax=Decimal("24.40"),
            products_with_tax=Decimal("20.00"),
            shipping_with_tax=Decimal("4.40"),
        ),
        net=CorrispettivoSplitTotalsSchema(
            total_with_tax=Decimal("97.60"),
            products_with_tax=Decimal("80.00"),
            shipping_with_tax=Decimal("17.60"),
        ),
    )
    summary = CorrispettivoListResponseSchema(
        year=2026,
        month=5,
        days=[day],
        month_totals=day.net,
    )

    workbook_bytes = CorrispettiviExcelService().build_workbook(summary)
    sheet = load_workbook(io.BytesIO(workbook_bytes)).active

    assert [cell.value for cell in sheet[1]] == CorrispettiviExcelService.HEADERS
    assert sheet[2][0].value == "2026-05-15"
    assert sheet[2][1].value == 24.4
    assert sheet[2][2].value == 97.6
    assert sheet[2][3].value == 80.0
    assert sheet[2][4].value == 17.6


def test_export_filters_without_country_strips_delivery_iso():
    from src.schemas.corrispettivo_schema import CorrispettivoFiltersSchema
    from src.services.routers.corrispettivo_service import CorrispettivoService

    filters = CorrispettivoFiltersSchema(id_store=1, delivery_country_iso="FR")
    result = CorrispettivoService._filters_without_country(filters)

    assert result is not None
    assert result.id_store == 1
    assert result.delivery_country_iso is None
