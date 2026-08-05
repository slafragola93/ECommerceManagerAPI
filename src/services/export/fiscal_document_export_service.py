"""Export massivo lista fatture (Excel, ZIP XML, CSV legacy)."""
from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import date, datetime
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence

from openpyxl import Workbook
from openpyxl.styles import Font

from src.schemas.fiscal_document_schema import (
    InvoiceListExportItemSchema,
    InvoiceResponseSchema,
)
from src.schemas.ricevuta_schema import (
    RicevutaAddressEmbedSchema,
    RicevutaOrderDetailEmbedSchema,
)


class FiscalDocumentExportService:
    LIST_HEADERS = [
        "id_fiscal_document",
        "document_type",
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

    # Header CSV legacy (EXPORT-nc / EXPORT fatture) — ordine e nomi esatti
    LEGACY_CSV_HEADERS = [
        "Documento",
        "Numero",
        "Data",
        "Ragione sociale",
        "Nome",
        "Cognome",
        "P.IVA",
        "C.F.",
        "Indirizzo 1",
        "Indirizzo 2",
        "CAP",
        "Città",
        "Tel 1",
        "Tel 2",
        "Mail",
        "Provincia",
        "Nazione",
        "Peso",
        "Totale",
        "Pagamento",
        "Metodo pagamento",
        "Conto pagamento",
        "Colli",
        "Note",
        "Spese trasporto",
        "Spese incasso",
        "Spese varie",
        "Scadenze",
        "Articolo",
        "Quantità",
        "Prezzo articolo",
        "Aliquota perc.",
        "Aliquota codice",
        "EAN",
        "SKU",
        "SKU Parent",
        "Riferimento",
    ]

    DOCUMENT_LABELS = {
        "credit_note": "NOTA CREDITO",
        "invoice": "FATTURA",
    }

    SCARTI_REPORT_FILENAME = "export-scarti.json"

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
            item.document_type,
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

    def build_list_xlsx(
        self,
        items: Iterable[InvoiceListExportItemSchema],
        *,
        sheet_title: str = "Fatture",
    ) -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = sheet_title
        sheet.append(self.LIST_HEADERS)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for item in items:
            sheet.append(self._list_row(item))

        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    @classmethod
    def _build_zip(
        cls,
        entries: Sequence[tuple[bytes, str]],
        duplicate_prefix: str,
        *,
        report: Optional[Dict[str, Any]] = None,
        report_filename: str = SCARTI_REPORT_FILENAME,
    ) -> bytes:
        buffer = io.BytesIO()
        used_names: set[str] = set()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for index, (payload, filename) in enumerate(entries, start=1):
                unique_name = filename
                if unique_name in used_names:
                    unique_name = (
                        f"{duplicate_prefix}-{index}"
                        f"{unique_name[unique_name.rfind('.'):]}"
                    )
                used_names.add(unique_name)
                archive.writestr(unique_name, payload)

            if report is not None:
                name = report_filename
                if name in used_names:
                    name = f"_{report_filename}"
                archive.writestr(
                    name,
                    json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"),
                )

        return buffer.getvalue()

    def build_xml_zip(
        self,
        invoice_ids: Sequence[int],
        xml_loader: Callable[[int], tuple[bytes, str]],
        *,
        duplicate_prefix: str = "fattura",
        scarti_report: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """
        Crea ZIP con un XML FatturaPA per ogni documento.

        xml_loader: callable(id_fiscal_document) -> (bytes, filename)
        scarti_report: se presente, aggiunto come ``export-scarti.json`` (export soft).
        """
        entries = [xml_loader(invoice_id) for invoice_id in invoice_ids]
        return self._build_zip(
            entries,
            duplicate_prefix,
            report=scarti_report,
        )

    # ------------------------------------------------------------------
    # CSV legacy (formato EXPORT-nc / contabilità)
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_date(value: Optional[datetime | date]) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.strftime("%d/%m/%Y")
        return value.strftime("%d/%m/%Y")

    @staticmethod
    def _fmt_money(value: Optional[float]) -> str:
        if value is None:
            return "0,00"
        return f"{float(value):.2f}".replace(".", ",")

    @staticmethod
    def _fmt_weight(value: Optional[float]) -> str:
        if value is None:
            return "0"
        number = float(value)
        if number == int(number):
            return str(int(number))
        return f"{number:.5f}".rstrip("0").rstrip(".")

    @staticmethod
    def _fmt_tax_percent(value: Optional[float]) -> str:
        if value is None:
            return "0.00"
        return f"{float(value):.2f}"

    @staticmethod
    def _display_document_number(number: Optional[str]) -> str:
        if not number:
            return ""
        text = str(number).strip()
        if text.isdigit():
            return str(int(text))
        return text

    @staticmethod
    def _s(value: Optional[Any]) -> str:
        if value is None:
            return ""
        return str(value)

    @classmethod
    def _primary_address(
        cls, doc: InvoiceResponseSchema
    ) -> Optional[RicevutaAddressEmbedSchema]:
        return doc.address_invoice or doc.address_delivery

    @classmethod
    def _document_label(cls, document_type: str) -> str:
        return cls.DOCUMENT_LABELS.get(document_type, document_type.upper())

    @classmethod
    def _payment_status(cls, is_payed: bool) -> str:
        return "Pagato" if is_payed else "In attesa di pagamento"

    @classmethod
    def _payment_account(cls, payment_name: Optional[str]) -> str:
        return "Banca" if payment_name else ""

    @classmethod
    def _scadenze(cls, payment_due_date: Optional[date]) -> str:
        # Legacy EXPORT-nc usa sempre "[]"
        _ = payment_due_date
        return "[]"

    @classmethod
    def _riferimento(
        cls,
        doc: InvoiceResponseSchema,
        referenced_by_id: Mapping[int, InvoiceResponseSchema],
    ) -> str:
        if doc.document_type == "credit_note" and doc.id_fiscal_document_ref:
            ref = referenced_by_id.get(doc.id_fiscal_document_ref)
            if ref:
                num = cls._display_document_number(ref.document_number)
                data = cls._fmt_date(ref.date_add)
                if num and data:
                    return f"FATTURA n° {num} del {data}"
                if num:
                    return f"FATTURA n° {num}"
        return cls._s(doc.order_reference)

    @classmethod
    def _tax_fields(
        cls,
        line: RicevutaOrderDetailEmbedSchema,
        taxes_by_id: Mapping[int, Any],
    ) -> tuple[str, str]:
        tax = taxes_by_id.get(line.id_tax) if line.id_tax else None
        percentage = getattr(tax, "percentage", None) if tax is not None else None
        code = getattr(tax, "code", None) if tax is not None else None
        perc_str = cls._fmt_tax_percent(
            float(percentage) if percentage is not None else 0.0
        )
        if code is not None and str(code).strip() != "":
            code_str = str(code).strip()
        elif percentage is not None:
            code_str = str(int(float(percentage)))
        else:
            code_str = "0"
        return perc_str, code_str

    @classmethod
    def _product_lines(
        cls, doc: InvoiceResponseSchema
    ) -> list[RicevutaOrderDetailEmbedSchema]:
        return [line for line in (doc.order_details or []) if not line.is_shipping]

    @classmethod
    def _legacy_header_cells(cls, doc: InvoiceResponseSchema) -> list[str]:
        address = cls._primary_address(doc)
        customer = doc.customer
        payment_name = doc.payment.name if doc.payment else ""

        firstname = ""
        lastname = ""
        if address:
            firstname = address.firstname or ""
            lastname = address.lastname or ""
        if not firstname and customer:
            firstname = customer.firstname or ""
        if not lastname and customer:
            lastname = customer.lastname or ""

        return [
            cls._document_label(doc.document_type),
            cls._display_document_number(doc.document_number),
            cls._fmt_date(doc.date_add),
            cls._s(address.company if address else None),
            cls._s(firstname),
            cls._s(lastname),
            cls._s(address.vat if address else None),
            cls._s(address.dni if address else None),
            cls._s(address.address1 if address else None),
            cls._s(address.address2 if address else None),
            cls._s(address.postcode if address else None),
            cls._s(address.city if address else None),
            cls._s(address.phone if address else None),
            cls._s(address.mobile_phone if address else None),
            cls._s(customer.email if customer else None),
            cls._s(address.state if address else None),
            cls._s(
                address.country.iso_code
                if address and address.country
                else None
            ),
            cls._fmt_weight(doc.total_weight),
            cls._fmt_money(doc.total_price_with_tax),
            cls._payment_status(bool(doc.is_payed)),
            cls._s(payment_name),
            cls._payment_account(payment_name or None),
            "",  # Colli — non mappato in modo affidabile
            "",  # Note — legacy EXPORT-nc lascia vuoto
            cls._fmt_money(doc.shipping_total_price_with_tax),
            "0,00",  # Spese incasso
            "0,00",  # Spese varie
            cls._scadenze(doc.payment_due_date),
        ]

    @classmethod
    def _legacy_line_cells(
        cls,
        doc: InvoiceResponseSchema,
        line: Optional[RicevutaOrderDetailEmbedSchema],
        taxes_by_id: Mapping[int, Any],
        referenced_by_id: Mapping[int, InvoiceResponseSchema],
    ) -> list[str]:
        header = cls._legacy_header_cells(doc)
        if line is None:
            article = ["", "", "", "0.00", "0", "", "", "", cls._riferimento(doc, referenced_by_id)]
            return header + article

        perc, code = cls._tax_fields(line, taxes_by_id)
        sku = cls._s(line.product_reference)
        return header + [
            cls._s(line.product_name),
            cls._s(line.product_qty),
            cls._fmt_money(line.unit_price_with_tax),
            perc,
            code,
            "",  # EAN — non presente a catalogo
            sku,
            sku,  # SKU Parent = SKU (comportamento legacy)
            cls._riferimento(doc, referenced_by_id),
        ]

    def _iter_legacy_rows(
        self,
        documents: Iterable[InvoiceResponseSchema],
        taxes_by_id: Mapping[int, Any],
        referenced_by_id: Mapping[int, InvoiceResponseSchema],
    ) -> list[list[str]]:
        rows: list[list[str]] = []
        for doc in documents:
            lines = self._product_lines(doc)
            if not lines:
                rows.append(
                    self._legacy_line_cells(doc, None, taxes_by_id, referenced_by_id)
                )
                continue
            for line in lines:
                rows.append(
                    self._legacy_line_cells(doc, line, taxes_by_id, referenced_by_id)
                )
        return rows

    def build_legacy_csv(
        self,
        documents: Iterable[InvoiceResponseSchema],
        *,
        taxes_by_id: Optional[Mapping[int, Any]] = None,
        referenced_by_id: Optional[Mapping[int, InvoiceResponseSchema]] = None,
    ) -> bytes:
        """
        CSV legacy a righe prodotto (header documento ripetuto).

        Formato allineato a EXPORT-nc.csv: delimiter `;`, tutti i campi quotati,
        header con trailing `;`, numeri monetari con virgola.
        """
        taxes = taxes_by_id or {}
        refs = referenced_by_id or {}
        buffer = io.StringIO()
        writer = csv.writer(
            buffer,
            delimiter=";",
            quoting=csv.QUOTE_ALL,
            lineterminator="\n",
        )
        # Header con trailing semicolon come nel file legacy
        buffer.write(";".join(self.LEGACY_CSV_HEADERS) + ";\n")

        for row in self._iter_legacy_rows(documents, taxes, refs):
            writer.writerow(row)

        return buffer.getvalue().encode("utf-8")

    def build_legacy_xlsx(
        self,
        documents: Iterable[InvoiceResponseSchema],
        *,
        taxes_by_id: Optional[Mapping[int, Any]] = None,
        referenced_by_id: Optional[Mapping[int, InvoiceResponseSchema]] = None,
        sheet_title: str = "Note di credito",
    ) -> bytes:
        """Excel con le stesse colonne italiane del CSV legacy (EXPORT-nc)."""
        taxes = taxes_by_id or {}
        refs = referenced_by_id or {}
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = sheet_title[:31]
        sheet.append(self.LEGACY_CSV_HEADERS)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for row in self._iter_legacy_rows(documents, taxes, refs):
            sheet.append(row)

        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()
