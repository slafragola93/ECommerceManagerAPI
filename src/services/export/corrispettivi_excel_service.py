from __future__ import annotations

import io
import zipfile
from decimal import Decimal
from typing import Dict

from openpyxl import Workbook
from openpyxl.styles import Font

from src.schemas.corrispettivo_schema import (
    CorrispettivoAmountSchema,
    CorrispettivoDaySummarySchema,
    CorrispettivoListResponseSchema,
    CorrispettivoRiepilogoResponseSchema,
    CorrispettivoTaxColumnSchema,
)


class CorrispettiviExcelService:
    HEADERS = [
        "Data",
        "Tot resi",
        "Totale netto",
        "Netto prodotti",
        "Netto spedizione",
    ]

    @staticmethod
    def _format_amount(value: Decimal | float) -> float:
        return round(float(value), 2)

    def _day_row(self, day: CorrispettivoDaySummarySchema) -> list:
        return [
            day.date.isoformat(),
            self._format_amount(day.returns.total_with_tax),
            self._format_amount(day.net.total_with_tax),
            self._format_amount(day.net.products_with_tax),
            self._format_amount(day.net.shipping_with_tax),
        ]

    def build_workbook(self, summary: CorrispettivoListResponseSchema) -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Registro"

        sheet.append(self.HEADERS)
        for cell in sheet[1]:
            cell.font = Font(bold=True)

        for day in summary.days:
            sheet.append(self._day_row(day))

        returns_total = sum(day.returns.total_with_tax for day in summary.days)
        sheet.append(
            [
                f"Totale {summary.month:02d}/{summary.year}",
                self._format_amount(returns_total),
                self._format_amount(summary.month_totals.total_with_tax),
                self._format_amount(summary.month_totals.products_with_tax),
                self._format_amount(summary.month_totals.shipping_with_tax),
            ]
        )

        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    @staticmethod
    def _zero_amount() -> CorrispettivoAmountSchema:
        return CorrispettivoAmountSchema()

    def _riepilogo_headers(self, columns: list[CorrispettivoTaxColumnSchema]) -> list[str]:
        headers = ["Data"]
        for column in columns:
            label = column.label
            headers.extend(
                [
                    f"{label} - Vendite",
                    f"{label} - Resi",
                    f"{label} - Netto",
                ]
            )
        headers.extend(
            [
                "Totale - Vendite",
                "Totale - Resi",
                "Totale - Netto",
                "Spedizione - Vendite",
                "Spedizione - Resi",
                "Spedizione - Netto",
            ]
        )
        return headers

    def _riepilogo_row_values(
        self,
        columns: list[CorrispettivoTaxColumnSchema],
        cells: dict[str, CorrispettivoAmountSchema],
        row_net: CorrispettivoAmountSchema,
        shipping: CorrispettivoAmountSchema,
    ) -> list:
        values: list = []
        for column in columns:
            amount = cells.get(str(column.id_tax), self._zero_amount())
            values.extend(
                [
                    self._format_amount(amount.sales_net),
                    self._format_amount(amount.returns_net),
                    self._format_amount(amount.net),
                ]
            )
        values.extend(
            [
                self._format_amount(row_net.sales_net),
                self._format_amount(row_net.returns_net),
                self._format_amount(row_net.net),
                self._format_amount(shipping.sales_net),
                self._format_amount(shipping.returns_net),
                self._format_amount(shipping.net),
            ]
        )
        return values

    def build_riepilogo_workbook(
        self, riepilogo: CorrispettivoRiepilogoResponseSchema
    ) -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Riepilogo"

        columns = riepilogo.columns
        sheet.append(self._riepilogo_headers(columns))
        for cell in sheet[1]:
            cell.font = Font(bold=True)

        for row in riepilogo.rows:
            sheet.append(
                [row.date.isoformat()]
                + self._riepilogo_row_values(
                    columns, row.cells, row.row_net, row.shipping
                )
            )

        month_tax_totals = {
            column.id_tax: CorrispettivoAmountSchema() for column in columns
        }
        month_shipping = CorrispettivoAmountSchema()
        for row in riepilogo.rows:
            for column in columns:
                amount = row.cells.get(str(column.id_tax), self._zero_amount())
                bucket = month_tax_totals[column.id_tax]
                bucket.sales_net += amount.sales_net
                bucket.returns_net += amount.returns_net
                bucket.net += amount.net
            month_shipping.sales_net += row.shipping.sales_net
            month_shipping.returns_net += row.shipping.returns_net
            month_shipping.net += row.shipping.net

        month_cells = {
            str(column.id_tax): month_tax_totals[column.id_tax] for column in columns
        }
        sheet.append(
            [f"Totale {riepilogo.month:02d}/{riepilogo.year}"]
            + self._riepilogo_row_values(
                columns,
                month_cells,
                riepilogo.month_totals,
                month_shipping,
            )
        )

        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    def build_registri_zip(
        self,
        consolidated_riepilogo: CorrispettivoRiepilogoResponseSchema,
        by_country: Dict[str, CorrispettivoListResponseSchema],
    ) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "registro.xlsx",
                self.build_riepilogo_workbook(consolidated_riepilogo),
            )
            for iso_code, summary in sorted(by_country.items()):
                archive.writestr(
                    f"registro_{iso_code}.xlsx",
                    self.build_workbook(summary),
                )
        return buffer.getvalue()
