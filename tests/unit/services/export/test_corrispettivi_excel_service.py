"""Test export Excel corrispettivi — colonne netti e resi."""
from datetime import date
from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook

from src.schemas.corrispettivo_schema import (
    CorrispettivoDaySummarySchema,
    CorrispettivoListResponseSchema,
    CorrispettivoSalesBreakdownSchema,
    CorrispettivoSplitTotalsSchema,
)
from src.services.export.corrispettivi_excel_service import CorrispettiviExcelService


def _split(
    total_with_tax: str,
    *,
    products_with_tax: str | None = None,
    shipping_with_tax: str | None = None,
) -> CorrispettivoSplitTotalsSchema:
    tw = Decimal(total_with_tax)
    pw = Decimal(products_with_tax if products_with_tax is not None else total_with_tax)
    sw = Decimal(shipping_with_tax if shipping_with_tax is not None else "0")
    return CorrispettivoSplitTotalsSchema(
        total_with_tax=tw,
        total_net=tw,
        products_with_tax=pw,
        products_net=pw,
        shipping_with_tax=sw,
        shipping_net=sw,
    )


class TestCorrispettiviExcelService:
    def test_headers_net_and_returns_only(self):
        service = CorrispettiviExcelService()
        assert service.HEADERS == [
            "Data",
            "Tot resi",
            "Totale netto",
            "Netto prodotti",
            "Netto spedizione",
        ]

    def test_workbook_row_uses_net_and_returns(self):
        day = CorrispettivoDaySummarySchema(
            date=date(2026, 7, 8),
            sales=_split("122.00"),
            returns=_split("10.00"),
            net=_split("112.00", products_with_tax="100.00", shipping_with_tax="12.00"),
            sales_breakdown=CorrispettivoSalesBreakdownSchema(
                base=_split("0"),
                ricevute_decurtazione=_split("0"),
                ricevute_imputazione=_split("122.00"),
            ),
        )
        summary = CorrispettivoListResponseSchema(
            year=2026,
            month=7,
            days=[day],
            month_totals=_split(
                "112.00", products_with_tax="100.00", shipping_with_tax="12.00"
            ),
        )

        raw = CorrispettiviExcelService().build_workbook(summary)
        sheet = load_workbook(BytesIO(raw)).active

        assert sheet.cell(2, 1).value == "2026-07-08"
        assert sheet.cell(2, 2).value == 10.0
        assert sheet.cell(2, 3).value == 112.0
        assert sheet.cell(2, 4).value == 100.0
        assert sheet.cell(2, 5).value == 12.0
        assert sheet.cell(3, 2).value == 10.0
        assert sheet.cell(3, 3).value == 112.0

    def test_zip_contains_registro_files(self):
        day = CorrispettivoDaySummarySchema(
            date=date(2026, 7, 15),
            sales=_split("50.00"),
            returns=_split("0"),
            net=_split("50.00"),
        )
        summary = CorrispettivoListResponseSchema(
            year=2026,
            month=7,
            days=[day],
            month_totals=_split("50.00"),
        )

        raw = CorrispettiviExcelService().build_registri_zip(
            consolidated=summary,
            by_country={"IT": summary},
        )

        import zipfile

        with zipfile.ZipFile(BytesIO(raw)) as archive:
            names = set(archive.namelist())
        assert "registro.xlsx" in names
        assert "registro_IT.xlsx" in names
