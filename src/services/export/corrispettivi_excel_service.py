from __future__ import annotations

import io
import zipfile
from decimal import Decimal
from typing import Dict

from openpyxl import Workbook
from openpyxl.styles import Font

from src.schemas.corrispettivo_schema import CorrispettivoRiepilogoResponseSchema


class CorrispettiviExcelService:
    @staticmethod
    def _format_amount(value: Decimal | float) -> float:
        return round(float(value), 2)

    def build_workbook(self, riepilogo: CorrispettivoRiepilogoResponseSchema) -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Riepilogo"

        headers = ["Giorno", "Data"]
        for column in riepilogo.columns:
            headers.extend([f"{column.label} Vendite", f"{column.label} Resi"])
        headers.extend(["Netto Vendite", "Netto Resi", "Netto", "Sped. Vendite", "Sped. Resi"])

        sheet.append(headers)
        for cell in sheet[1]:
            cell.font = Font(bold=True)

        for row in riepilogo.rows:
            line = [f"{row.day:02d}", row.date.isoformat()]
            for column in riepilogo.columns:
                cell_data = row.cells.get(str(column.id_tax))
                if cell_data:
                    line.extend(
                        [
                            self._format_amount(cell_data.sales_net),
                            self._format_amount(cell_data.returns_net),
                        ]
                    )
                else:
                    line.extend([0.0, 0.0])
            line.extend(
                [
                    self._format_amount(row.row_net.sales_net),
                    self._format_amount(row.row_net.returns_net),
                    self._format_amount(row.row_net.net),
                    self._format_amount(row.shipping.sales_net),
                    self._format_amount(row.shipping.returns_net),
                ]
            )
            sheet.append(line)

        totals_row = [
            "Totale",
            f"{riepilogo.month:02d}/{riepilogo.year}",
        ]
        for _ in riepilogo.columns:
            totals_row.extend(["", ""])
        totals_row.extend(
            [
                self._format_amount(riepilogo.month_totals.sales_net),
                self._format_amount(riepilogo.month_totals.returns_net),
                self._format_amount(riepilogo.month_totals.net),
                "",
                "",
            ]
        )
        sheet.append(totals_row)

        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    def build_registri_zip(
        self,
        consolidated: CorrispettivoRiepilogoResponseSchema,
        by_country: Dict[str, CorrispettivoRiepilogoResponseSchema],
    ) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("registro.xlsx", self.build_workbook(consolidated))
            for iso_code, riepilogo in sorted(by_country.items()):
                archive.writestr(f"registro_{iso_code}.xlsx", self.build_workbook(riepilogo))
        return buffer.getvalue()
