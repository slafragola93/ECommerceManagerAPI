from __future__ import annotations

import io
import zipfile
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Font

from src.schemas.corrispettivo_schema import (
    CorrispettivoRiepilogoResponseSchema,
    CorrispettivoTaxCellSchema,
    CorrispettivoTaxColumnSchema,
)


class CorrispettiviExcelService:
    @staticmethod
    def _format_date(value) -> str:
        return value.strftime("%d/%m/%Y")

    @staticmethod
    def _format_amount(value: Decimal | float) -> float:
        return round(float(value), 2)

    @staticmethod
    def _zero_cell() -> CorrispettivoTaxCellSchema:
        return CorrispettivoTaxCellSchema()

    def _riepilogo_headers(self, columns: list[CorrispettivoTaxColumnSchema]) -> list[str]:
        headers = ["Data"]
        for column in columns:
            label = column.label
            headers.extend(
                [
                    f"{label} - Totale entrate prodotti",
                    f"{label} - Totale entrata spedizione",
                    f"{label} - Totale resi prodotti",
                    f"{label} - Totale resi spedizione",
                ]
            )
        return headers

    def _riepilogo_row_values(
        self,
        columns: list[CorrispettivoTaxColumnSchema],
        cells: dict[str, CorrispettivoTaxCellSchema],
    ) -> list:
        values: list = []
        for column in columns:
            cell = cells.get(str(column.id_tax), self._zero_cell())
            values.extend(
                [
                    self._format_amount(cell.products_sales),
                    self._format_amount(cell.shipping_sales),
                    self._format_amount(cell.products_returns),
                    self._format_amount(cell.shipping_returns),
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
                [self._format_date(row.date)]
                + self._riepilogo_row_values(columns, row.cells)
            )

        month_cells = {
            str(column.id_tax): CorrispettivoTaxCellSchema() for column in columns
        }
        for row in riepilogo.rows:
            for column in columns:
                cell = row.cells.get(str(column.id_tax), self._zero_cell())
                bucket = month_cells[str(column.id_tax)]
                bucket.products_sales += cell.products_sales
                bucket.shipping_sales += cell.shipping_sales
                bucket.products_returns += cell.products_returns
                bucket.shipping_returns += cell.shipping_returns

        sheet.append(
            [f"Totale {riepilogo.month:02d}/{riepilogo.year}"]
            + self._riepilogo_row_values(columns, month_cells)
        )

        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    def build_registri_zip(
        self,
        consolidated_riepilogo: CorrispettivoRiepilogoResponseSchema,
        by_country: dict[str, CorrispettivoRiepilogoResponseSchema],
    ) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "registro.xlsx",
                self.build_riepilogo_workbook(consolidated_riepilogo),
            )
            for iso_code, riepilogo in sorted(by_country.items()):
                archive.writestr(
                    f"registro_{iso_code}.xlsx",
                    self.build_riepilogo_workbook(riepilogo),
                )
        return buffer.getvalue()
