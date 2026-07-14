"""Test export Excel corrispettivi — colonne netti e resi."""
from datetime import date
from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook

from src.schemas.corrispettivo_schema import (
    CorrispettivoAmountSchema,
    CorrispettivoDaySummarySchema,
    CorrispettivoListResponseSchema,
    CorrispettivoRiepilogoResponseSchema,
    CorrispettivoRiepilogoRowSchema,
    CorrispettivoSalesBreakdownSchema,
    CorrispettivoShippingDaySchema,
    CorrispettivoSplitTotalsSchema,
    CorrispettivoTaxColumnSchema,
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
        riepilogo = CorrispettivoRiepilogoResponseSchema(
            year=2026,
            month=7,
            columns=[CorrispettivoTaxColumnSchema(id_tax=1, label="22", percentage=22.0)],
            rows=[
                CorrispettivoRiepilogoRowSchema(
                    day=15,
                    date=date(2026, 7, 15),
                    cells={
                        "1": CorrispettivoAmountSchema(
                            sales_net=Decimal("50.00"),
                            returns_net=Decimal("0"),
                            net=Decimal("50.00"),
                        )
                    },
                    row_net=CorrispettivoAmountSchema(
                        sales_net=Decimal("50.00"),
                        returns_net=Decimal("0"),
                        net=Decimal("50.00"),
                    ),
                    shipping=CorrispettivoShippingDaySchema(),
                )
            ],
            month_totals=CorrispettivoAmountSchema(
                sales_net=Decimal("50.00"),
                returns_net=Decimal("0"),
                net=Decimal("50.00"),
            ),
        )

        raw = CorrispettiviExcelService().build_registri_zip(
            consolidated_riepilogo=riepilogo,
            by_country={"IT": summary},
        )

        import zipfile

        with zipfile.ZipFile(BytesIO(raw)) as archive:
            names = set(archive.namelist())
        assert "registro.xlsx" in names
        assert "registro_IT.xlsx" in names

    def test_riepilogo_workbook_includes_tax_columns(self):
        riepilogo = CorrispettivoRiepilogoResponseSchema(
            year=2026,
            month=7,
            columns=[
                CorrispettivoTaxColumnSchema(id_tax=1, label="22", percentage=22.0),
                CorrispettivoTaxColumnSchema(id_tax=9, label="0", percentage=0.0),
            ],
            rows=[
                CorrispettivoRiepilogoRowSchema(
                    day=8,
                    date=date(2026, 7, 8),
                    cells={
                        "1": CorrispettivoAmountSchema(
                            sales_net=Decimal("100.00"),
                            returns_net=Decimal("10.00"),
                            net=Decimal("90.00"),
                        ),
                        "9": CorrispettivoAmountSchema(
                            sales_net=Decimal("20.00"),
                            returns_net=Decimal("0"),
                            net=Decimal("20.00"),
                        ),
                    },
                    row_net=CorrispettivoAmountSchema(
                        sales_net=Decimal("120.00"),
                        returns_net=Decimal("10.00"),
                        net=Decimal("110.00"),
                    ),
                    shipping=CorrispettivoShippingDaySchema(
                        sales_net=Decimal("12.00"),
                        returns_net=Decimal("2.00"),
                        net=Decimal("10.00"),
                    ),
                )
            ],
            month_totals=CorrispettivoAmountSchema(
                sales_net=Decimal("120.00"),
                returns_net=Decimal("10.00"),
                net=Decimal("110.00"),
            ),
        )

        raw = CorrispettiviExcelService().build_riepilogo_workbook(riepilogo)
        sheet = load_workbook(BytesIO(raw)).active

        assert sheet.title == "Riepilogo"
        assert sheet.cell(1, 1).value == "Data"
        assert sheet.cell(1, 2).value == "22 - Vendite"
        assert sheet.cell(1, 5).value == "0 - Vendite"
        assert sheet.cell(1, 8).value == "Totale - Vendite"
        assert sheet.cell(1, 11).value == "Spedizione - Vendite"
        assert sheet.cell(2, 1).value == "2026-07-08"
        assert sheet.cell(2, 2).value == 100.0
        assert sheet.cell(2, 3).value == 10.0
        assert sheet.cell(2, 4).value == 90.0
        assert sheet.cell(2, 5).value == 20.0
        assert sheet.cell(2, 8).value == 120.0
        assert sheet.cell(2, 11).value == 12.0
        assert sheet.cell(3, 1).value == "Totale 07/2026"
        assert sheet.cell(3, 4).value == 90.0
        assert sheet.cell(3, 13).value == 10.0
