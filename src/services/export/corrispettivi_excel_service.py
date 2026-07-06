from __future__ import annotations

import io
import zipfile
from decimal import Decimal
from typing import Dict

from openpyxl import Workbook
from openpyxl.styles import Font

from src.schemas.corrispettivo_schema import CorrispettivoListResponseSchema


class CorrispettiviExcelService:
    HEADERS = [
        "Data",
        "Totale vendite",
        "Tot resi",
        "Totale netto",
        "Netto prodotti",
        "Netto spedizione",
    ]

    @staticmethod
    def _format_amount(value: Decimal | float) -> float:
        return round(float(value), 2)

    def build_workbook(self, summary: CorrispettivoListResponseSchema) -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Registro"

        sheet.append(self.HEADERS)
        for cell in sheet[1]:
            cell.font = Font(bold=True)

        for day in summary.days:
            sheet.append(
                [
                    day.date.isoformat(),
                    self._format_amount(day.sales.total_with_tax),
                    self._format_amount(day.returns.total_with_tax),
                    self._format_amount(day.net.total_with_tax),
                    self._format_amount(day.net.products_with_tax),
                    self._format_amount(day.net.shipping_with_tax),
                ]
            )

        sales_total = sum(day.sales.total_with_tax for day in summary.days)
        returns_total = sum(day.returns.total_with_tax for day in summary.days)
        sheet.append(
            [
                f"Totale {summary.month:02d}/{summary.year}",
                self._format_amount(sales_total),
                self._format_amount(returns_total),
                self._format_amount(summary.month_totals.total_with_tax),
                self._format_amount(summary.month_totals.products_with_tax),
                self._format_amount(summary.month_totals.shipping_with_tax),
            ]
        )

        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    def build_registri_zip(
        self,
        consolidated: CorrispettivoListResponseSchema,
        by_country: Dict[str, CorrispettivoListResponseSchema],
    ) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("registro.xlsx", self.build_workbook(consolidated))
            for iso_code, summary in sorted(by_country.items()):
                archive.writestr(
                    f"registro_{iso_code}.xlsx",
                    self.build_workbook(summary),
                )
        return buffer.getvalue()
