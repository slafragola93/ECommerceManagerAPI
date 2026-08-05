"""Test export massivo fatture."""
from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from src.schemas.fiscal_document_schema import (
    InvoiceExportFiltersSchema,
    InvoiceListExportItemSchema,
    InvoiceResponseSchema,
)
from src.schemas.ricevuta_schema import (
    RicevutaAddressEmbedSchema,
    RicevutaCountryEmbedSchema,
    RicevutaCustomerEmbedSchema,
    RicevutaOrderDetailEmbedSchema,
    RicevutaPaymentEmbedSchema,
)
from src.services.export.fiscal_document_export_service import FiscalDocumentExportService


def _sample_item(**overrides) -> InvoiceListExportItemSchema:
    data = {
        "id_fiscal_document": 1,
        "document_type": "invoice",
        "document_number": "000001",
        "internal_number": None,
        "tipo_documento_fe": "TD01",
        "status": "issued",
        "is_electronic": True,
        "id_order": 100,
        "order_reference": "ORD-100",
        "customer_firstname": "Mario",
        "customer_lastname": "Rossi",
        "customer_email": "mario@example.com",
        "delivery_country_iso": "IT",
        "delivery_city": "Roma",
        "date_add": datetime(2026, 1, 15, 10, 30, 0),
        "total_price_net": 100.0,
        "total_price_with_tax": 122.0,
        "products_total_price_net": 90.0,
        "products_total_price_with_tax": 109.8,
    }
    data.update(overrides)
    return InvoiceListExportItemSchema(**data)


class TestFiscalDocumentExportService:
    def setup_method(self):
        self.service = FiscalDocumentExportService()

    def test_build_list_xlsx_headers_and_row(self):
        content = self.service.build_list_xlsx([_sample_item()])
        workbook = load_workbook(io.BytesIO(content))
        sheet = workbook.active

        assert sheet.title == "Fatture"
        assert sheet.max_row == 2
        assert sheet.cell(row=1, column=1).value == "id_fiscal_document"
        assert sheet.cell(row=1, column=2).value == "document_type"
        assert sheet.cell(row=2, column=2).value == "invoice"
        assert sheet.cell(row=2, column=3).value == "000001"
        assert sheet.cell(row=2, column=10).value == "Mario Rossi"
        assert sheet.cell(row=2, column=15).value == 100.0

    def test_build_xml_zip_contains_files(self):
        def fake_loader(invoice_id: int) -> tuple[bytes, str]:
            return b"<?xml version='1.0'?>", f"IT01234567890_{invoice_id:05d}.xml"

        content = self.service.build_xml_zip([1, 2], fake_loader)
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = sorted(archive.namelist())
            assert names == ["IT01234567890_00001.xml", "IT01234567890_00002.xml"]

    def test_build_xml_zip_includes_scarti_report_when_partial(self):
        def fake_loader(invoice_id: int) -> tuple[bytes, str]:
            return b"<xml/>", f"IT01234567890_{invoice_id:05d}.xml"

        report = {
            "partial": True,
            "exported_count": 1,
            "failed_count": 2,
            "failed": [{"id_fiscal_document": 70, "message": "P.IVA non valida"}],
        }
        content = self.service.build_xml_zip(
            [1], fake_loader, scarti_report=report
        )
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
            assert "IT01234567890_00001.xml" in names
            assert "export-scarti.json" in names
            payload = json.loads(archive.read("export-scarti.json").decode("utf-8"))
            assert payload["partial"] is True
            assert payload["failed_count"] == 2


def _sample_credit_note(**overrides) -> InvoiceResponseSchema:
    data = {
        "id_fiscal_document": 50,
        "document_type": "credit_note",
        "tipo_documento_fe": "TD04",
        "id_order": 100,
        "id_fiscal_document_ref": 10,
        "document_number": "000203",
        "status": "issued",
        "is_electronic": True,
        "credit_note_reason": None,
        "is_partial": False,
        "includes_shipping": True,
        "total_price_with_tax": 34.21,
        "total_price_net": 28.04,
        "products_total_price_net": 17.93,
        "products_total_price_with_tax": 21.92,
        "date_add": datetime(2026, 5, 30, 12, 0, 0),
        "total_weight": 0.144,
        "is_payed": False,
        "payment": RicevutaPaymentEmbedSchema(id_payment=1, name="Klarna_VIES"),
        "shipping_total_price_with_tax": 12.29,
        "customer": RicevutaCustomerEmbedSchema(
            id_customer=1,
            firstname="Nikoll",
            lastname="Baftiaj",
            email="niko.baftiaj@gmail.com",
        ),
        "address_invoice": RicevutaAddressEmbedSchema(
            id_address=1,
            company="ProSan Haustechnik",
            firstname="Nikoll",
            lastname="Baftiaj",
            address1="Triesterstrasse 128a",
            address2="",
            city="Graz",
            postcode="08020",
            state="",
            phone="",
            mobile_phone="06766714551",
            vat="ATU83059967",
            dni="",
            country=RicevutaCountryEmbedSchema(iso_code="AT", name="Austria"),
        ),
        "order_details": [
            RicevutaOrderDetailEmbedSchema(
                id_order_detail=1,
                id_product=1,
                product_name="Cartuccia per miscelatori Paffoni",
                product_reference="PAF ZA91104R",
                product_qty=1,
                id_tax=2,
                unit_price_with_tax=9.61,
                total_price_with_tax=9.61,
                is_shipping=False,
            ),
            RicevutaOrderDetailEmbedSchema(
                id_order_detail=2,
                id_product=2,
                product_name="Cartuccia aperta Paffoni",
                product_reference="PAF ZA91191",
                product_qty=1,
                id_tax=2,
                unit_price_with_tax=12.31,
                total_price_with_tax=12.31,
                is_shipping=False,
            ),
            RicevutaOrderDetailEmbedSchema(
                id_order_detail=0,
                product_name="Spedizione",
                product_reference="SHIPPING",
                product_qty=1,
                unit_price_with_tax=12.29,
                total_price_with_tax=12.29,
                is_shipping=True,
            ),
        ],
    }
    data.update(overrides)
    return InvoiceResponseSchema(**data)


class TestFiscalDocumentLegacyCsv:
    def setup_method(self):
        self.service = FiscalDocumentExportService()

    def test_legacy_csv_headers_match_export_nc(self):
        content = self.service.build_legacy_csv([])
        text = content.decode("utf-8")
        first_line = text.splitlines()[0]
        assert first_line.endswith(";")
        assert first_line.startswith("Documento;Numero;Data;Ragione sociale;")
        assert "Aliquota perc.;Aliquota codice;EAN;SKU;SKU Parent;Riferimento;" in first_line
        assert first_line == ";".join(FiscalDocumentExportService.LEGACY_CSV_HEADERS) + ";"

    def test_credit_note_rows_match_legacy_fields(self):
        ref_invoice = InvoiceResponseSchema(
            id_fiscal_document=10,
            document_type="invoice",
            id_order=100,
            document_number="0005326",
            status="issued",
            is_electronic=True,
            includes_shipping=True,
            date_add=datetime(2026, 4, 27, 10, 0, 0),
        )
        tax = SimpleNamespace(id_tax=2, percentage=0, code="0")
        content = self.service.build_legacy_csv(
            [_sample_credit_note()],
            taxes_by_id={2: tax},
            referenced_by_id={10: ref_invoice},
        )
        rows = list(csv.reader(io.StringIO(content.decode("utf-8")), delimiter=";"))
        assert len(rows) == 3  # header + 2 product lines (shipping excluded)
        assert rows[0][0] == "Documento"
        assert rows[1][0] == "NOTA CREDITO"
        assert rows[1][1] == "203"
        assert rows[1][2] == "30/05/2026"
        assert rows[1][3] == "ProSan Haustechnik"
        assert rows[1][6] == "ATU83059967"
        assert rows[1][10] == "08020"
        assert rows[1][13] == "06766714551"
        assert rows[1][16] == "AT"
        assert rows[1][17] == "0.144"
        assert rows[1][18] == "34,21"
        assert rows[1][19] == "In attesa di pagamento"
        assert rows[1][20] == "Klarna_VIES"
        assert rows[1][21] == "Banca"
        assert rows[1][24] == "12,29"
        assert rows[1][25] == "0,00"
        assert rows[1][27] == "[]"
        assert rows[1][28] == "Cartuccia per miscelatori Paffoni"
        assert rows[1][29] == "1"
        assert rows[1][30] == "9,61"
        assert rows[1][31] == "0.00"
        assert rows[1][32] == "0"
        assert rows[1][34] == "PAF ZA91104R"
        assert rows[1][35] == "PAF ZA91104R"
        assert rows[1][36] == "FATTURA n° 5326 del 27/04/2026"
        assert rows[2][28] == "Cartuccia aperta Paffoni"
        assert rows[2][30] == "12,31"

    def test_legacy_xlsx_uses_same_italian_headers(self):
        content = self.service.build_legacy_xlsx([_sample_credit_note()])
        workbook = load_workbook(io.BytesIO(content))
        sheet = workbook.active
        headers = [cell.value for cell in sheet[1]]
        assert headers == FiscalDocumentExportService.LEGACY_CSV_HEADERS
        assert sheet.cell(row=2, column=1).value == "NOTA CREDITO"
        assert sheet.cell(row=2, column=2).value == "203"
        assert sheet.max_row == 3  # header + 2 product lines


class TestInvoiceExportFiltersSchema:
    def test_invalid_date_range(self):
        with pytest.raises(ValueError, match="date_add_to"):
            InvoiceExportFiltersSchema(
                date_add_from=datetime(2026, 2, 1).date(),
                date_add_to=datetime(2026, 1, 1).date(),
            )

    def test_normalizes_delivery_country_iso(self):
        filters = InvoiceExportFiltersSchema(delivery_country_iso="it")
        assert filters.delivery_country_iso == "IT"

    def test_normalizes_document_type(self):
        filters = InvoiceExportFiltersSchema(document_type="CREDIT_NOTE")
        assert filters.document_type == "credit_note"

    def test_for_xml_export_strips_extra_filters(self):
        source = InvoiceExportFiltersSchema(
            is_electronic=True,
            status="pending",
            id_order=10,
            id_customer=20,
            delivery_country_iso="DE",
            date_add_from=datetime(2026, 1, 1).date(),
            date_add_to=datetime(2026, 1, 31).date(),
        )
        xml_filters = source.for_xml_export(max_limit=5000)
        assert xml_filters.is_electronic is True
        assert xml_filters.status is None
        assert xml_filters.id_order is None
        assert xml_filters.id_customer is None
        assert xml_filters.delivery_country_iso == "DE"
        assert xml_filters.date_add_from.isoformat() == "2026-01-01"
        assert xml_filters.limit == 5000
