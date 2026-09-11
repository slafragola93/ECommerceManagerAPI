"""Unit test — ProgressivoInvio dedicato, distinto da Numero commerciale."""
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

import pytest

from src.models.tax import Tax
from src.services.external.fatturapa_progressivo import (
    format_progressivo_invio,
    next_progressivo_from_values,
    parse_progressivo_invio,
)
from src.services.external.fatturapa_service import FatturaPAService
from src.services.external.fatturapa_tax_line import (
    enrich_line_item_tax_fields,
    resolve_line_tax,
)


class TestProgressivoHelpers:
    def test_format_pads_six(self):
        assert format_progressivo_invio(1) == "000001"
        assert format_progressivo_invio(42) == "000042"

    def test_format_rejects_zero(self):
        with pytest.raises(ValueError):
            format_progressivo_invio(0)

    def test_next_from_mixed_values(self):
        assert next_progressivo_from_values(["000001", None, "000010", "abc"]) == (
            "000011"
        )

    def test_next_from_empty_starts_at_one(self):
        assert next_progressivo_from_values([]) == "000001"

    def test_parse_non_numeric(self):
        assert parse_progressivo_invio("  ") is None
        assert parse_progressivo_invio("12A") is None


@pytest.fixture
def fatturapa_service():
    svc = FatturaPAService.__new__(FatturaPAService)
    svc.db = MagicMock()
    svc.vat_number = "08632861210"
    svc.company_fiscal_code = "08632861210"
    svc.company_name = "Test Srl"
    svc.company_address = "Via Roma"
    svc.company_civic = "1"
    svc.company_cap = "20100"
    svc.company_city = "Milano"
    svc.company_province = "MI"
    svc.company_phone = "0212345678"
    svc.company_email = "test@example.com"
    svc.company_contact = "Admin"
    svc.company_iban = None
    svc.company_bank_name = None
    svc._td04_include_payment_due_date = lambda: False
    svc._payment_term_days = lambda: 30
    svc._get_config_value = lambda *a, **k: None
    return svc


def _line():
    return enrich_line_item_tax_fields(
        {
            "product_name": "Prodotto",
            "product_qty": 1,
            "product_price": 100.0,
            "reduction_percent": 0,
            "reduction_amount": 0,
            "id_tax": 1,
        },
        resolve_line_tax(
            Tax(percentage=22, electronic_code="", note=""),
            vies_eligible=False,
            is_product_line=True,
        ),
    )


def _order(**overrides):
    data = {
        "invoice_firstname": "Mario",
        "invoice_lastname": "Rossi",
        "invoice_company": "",
        "customer_fiscal_code": "RSSMRA80A01F205X",
        "invoice_pec": "",
        "invoice_sdi": "0000000",
        "invoice_vat": "",
        "invoice_address1": "Via Test 1",
        "invoice_postcode": "20100",
        "invoice_city": "Milano",
        "invoice_state": "MI",
        "country_iso": "IT",
        "tipo_documento_fe": "TD01",
        "total_price": 122.0,
        "document_date": "2026-08-21",
        "progressivo_invio": "000099",
    }
    data.update(overrides)
    return data


class TestGenerateXmlProgressivoVsNumero:
    def test_progressivo_invio_differs_from_numero(self, fatturapa_service):
        xml = fatturapa_service._generate_xml(
            _order(), [_line()], "00001", include_shipping=False
        )
        root = ET.fromstring(xml)
        progressivo = next(
            el.text for el in root.iter() if el.tag.endswith("ProgressivoInvio")
        )
        numero = next(el.text for el in root.iter() if el.tag.endswith("Numero"))
        assert progressivo == "000099"
        assert numero == "1"

    def test_filename_uses_progressivo(self, fatturapa_service):
        name = fatturapa_service._generate_filename("000099")
        assert name == "IT08632861210_000099.xml"
