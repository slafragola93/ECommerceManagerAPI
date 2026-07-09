"""Test export Excel corrispettivi — colonne breakdown ricevute."""
from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
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
    def test_headers_include_ricevute_breakdown_columns(self):
        service = CorrispettiviExcelService()
        assert service.HEADERS == [
            "Data",
            "Vendite base",
            "Ricevute decurtazione",
            "Ricevute imputazione",
            "Totale vendite",
            "Tot resi",
            "Totale netto",
            "Netto prodotti",
            "Netto spedizione",
        ]

    def test_workbook_row_with_sales_breakdown(self):
        day = CorrispettivoDaySummarySchema(
            date=date(2026, 7, 8),
            sales=_split("122.00"),
            returns=_split("0"),
            net=_split("122.00"),
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
            month_totals=_split("122.00"),
        )

        raw = CorrispettiviExcelService().build_workbook(summary)
        sheet = load_workbook(BytesIO(raw)).active

        assert sheet.cell(1, 2).value == "Vendite base"
        assert sheet.cell(1, 3).value == "Ricevute decurtazione"
        assert sheet.cell(1, 4).value == "Ricevute imputazione"
        assert sheet.cell(2, 1).value == "2026-07-08"
        assert sheet.cell(2, 2).value == 0.0
        assert sheet.cell(2, 3).value == 0.0
        assert sheet.cell(2, 4).value == 122.0
        assert sheet.cell(2, 5).value == 122.0
        assert sheet.cell(3, 4).value == 122.0

    def test_workbook_without_sales_breakdown_puts_all_in_base(self):
        day = CorrispettivoDaySummarySchema(
            date=date(2026, 7, 15),
            sales=_split("50.00"),
            returns=_split("0"),
            net=_split("50.00"),
            sales_breakdown=None,
        )
        summary = CorrispettivoListResponseSchema(
            year=2026,
            month=7,
            days=[day],
            month_totals=_split("50.00"),
        )

        raw = CorrispettiviExcelService().build_workbook(summary)
        sheet = load_workbook(BytesIO(raw)).active

        assert sheet.cell(2, 2).value == 50.0
        assert sheet.cell(2, 3).value == 0.0
        assert sheet.cell(2, 4).value == 0.0
        assert sheet.cell(2, 5).value == 50.0
