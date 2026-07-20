"""Export massivo lista fatture (Excel, ZIP XML)."""
from __future__ import annotations

import io
import zipfile
from typing import Callable, Iterable, Sequence

from openpyxl import Workbook
from openpyxl.styles import Font

from src.schemas.fiscal_document_schema import InvoiceListExportItemSchema


class FiscalDocumentExportService:
    LIST_HEADERS = [
        "id_fiscal_document",
        "document_number",
        "internal_number",
        "tipo_documento_fe",
        "status",
        "is_electronic",
        "id_order",
        "order_reference",
        "customer_name",
        "customer_email",
        "delivery_country",
        "delivery_city",
        "date_add",
        "total_price_net",
        "total_price_with_tax",
        "products_total_price_net",
        "products_total_price_with_tax",
    ]
    @staticmethod
    def _customer_name(item: InvoiceListExportItemSchema) -> str:
        return " ".join(
            part
            for part in (item.customer_firstname, item.customer_lastname)
            if part
        ).strip()

    @classmethod
    def _list_row(cls, item: InvoiceListExportItemSchema) -> list:
        date_add = item.date_add.isoformat(sep=" ") if item.date_add else None
        return [
            item.id_fiscal_document,
            item.document_number,
            item.internal_number,
            item.tipo_documento_fe,
            item.status,
            item.is_electronic,
            item.id_order,
            item.order_reference,
            cls._customer_name(item) or None,
            item.customer_email,
            item.delivery_country_iso,
            item.delivery_city,
            date_add,
            item.total_price_net,
            item.total_price_with_tax,
            item.products_total_price_net,
            item.products_total_price_with_tax,
        ]

    def build_list_xlsx(self, items: Iterable[InvoiceListExportItemSchema]) -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Fatture"
        sheet.append(self.LIST_HEADERS)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for item in items:
            sheet.append(self._list_row(item))

        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    @staticmethod
    def _build_zip(
        entries: Sequence[tuple[bytes, str]],
        duplicate_prefix: str,
    ) -> bytes:
        buffer = io.BytesIO()
        used_names: set[str] = set()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for index, (payload, filename) in enumerate(entries, start=1):
                unique_name = filename
                if unique_name in used_names:
                    unique_name = f"{duplicate_prefix}-{index}{unique_name[unique_name.rfind('.'):]}"
                used_names.add(unique_name)
                archive.writestr(unique_name, payload)

        return buffer.getvalue()

    def build_xml_zip(
        self,
        invoice_ids: Sequence[int],
        xml_loader: Callable[[int], tuple[bytes, str]],
    ) -> bytes:
        """
        Crea ZIP con un XML FatturaPA per ogni fattura.

        xml_loader: callable(id_fiscal_document) -> (bytes, filename)
        """
        entries = [xml_loader(invoice_id) for invoice_id in invoice_ids]
        return self._build_zip(entries, "fattura")
