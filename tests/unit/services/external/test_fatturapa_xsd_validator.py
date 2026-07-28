"""Unit test — validazione XSD ufficiale FatturaPA v1.2 (BE-PA-P0-02)."""
from unittest.mock import MagicMock

import pytest

from src.models.tax import Tax
from src.services.external.fatturapa_service import FatturaPAService
from src.services.external.fatturapa_tax_line import (
    VIES_DEFAULT_NORMATIVO,
    enrich_line_item_tax_fields,
    resolve_line_tax,
)
from src.services.external.fatturapa_xsd_validator import (
    clear_schema_cache,
    get_xsd_path,
    validate_fatturapa_xml,
)


@pytest.fixture(autouse=True)
def _clear_xsd_cache():
    clear_schema_cache()
    yield
    clear_schema_cache()


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
    svc.company_iban = "IT60X0542811101000000123456"
    svc.company_bank_name = "Banca Test"
    svc._get_config_value = lambda *a, **k: "RF01"
    return svc


def _line_22():
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


class TestFatturaPAXsdValidator:
    def test_xsd_file_is_vendored(self):
        path = get_xsd_path()
        assert path.is_file()
        assert path.stat().st_size > 1000

    def test_invalid_xml_fails(self):
        result = validate_fatturapa_xml("<root/>")
        assert result["valid"] is False
        assert result["errors"]
        assert result["errors"][0]["rule"] in ("xsd", "xsd_syntax")

    def test_generated_td01_italy_passes_xsd(self, fatturapa_service):
        order_data = {
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
            "total_discounts": 0,
            "shipping_price_tax_excl": 0,
            "document_date": "2026-07-10",
            "condizioni_pagamento": "TP02",
            "fiscal_mode_payment": "MP05",
            "date_add": "2026-07-01 10:00:00",
        }
        xml = fatturapa_service._generate_xml(
            order_data, [_line_22()], "00001", include_shipping=False
        )
        result = validate_fatturapa_xml(xml)
        assert result["valid"] is True, result["errors"]

    def test_generated_td04_and_foreign_pass_xsd(self, fatturapa_service):
        order_nc = {
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
            "tipo_documento_fe": "TD04",
            "total_price": 122.0,
            "total_discounts": 0,
            "shipping_price_tax_excl": 0,
            "document_date": "2026-07-15",
            "linked_invoice_number": "00020",
            "linked_invoice_date": "2026-07-10",
            "condizioni_pagamento": "TP02",
            "fiscal_mode_payment": "MP05",
            "date_add": "2026-07-01 10:00:00",
        }
        xml_nc = fatturapa_service._generate_xml(
            order_nc, [_line_22()], "00021", include_shipping=False
        )
        assert validate_fatturapa_xml(xml_nc)["valid"] is True

        line_vies = enrich_line_item_tax_fields(
            {
                "product_name": "UE",
                "product_qty": 1,
                "product_price": 100.0,
                "reduction_percent": 0,
                "reduction_amount": 0,
                "id_tax": 1,
            },
            resolve_line_tax(
                Tax(
                    percentage=0,
                    electronic_code="N3.2",
                    note=VIES_DEFAULT_NORMATIVO,
                ),
                vies_eligible=True,
                is_product_line=True,
            ),
        )
        order_fr = {
            "invoice_firstname": "",
            "invoice_lastname": "",
            "invoice_company": "L Oreal",
            "customer_fiscal_code": "",
            "invoice_pec": "",
            "invoice_sdi": "",
            "invoice_vat": "FR12345678901",
            "invoice_address1": "41 Rue Martre",
            "invoice_postcode": "75002",
            "invoice_city": "Clichy",
            "invoice_state": "Paris",
            "country_iso": "FR",
            "tipo_documento_fe": "TD01",
            "total_price": 100.0,
            "total_discounts": 0,
            "shipping_price_tax_excl": 0,
            "document_date": "2026-07-10",
            "vies_status": "eligible",
            "condizioni_pagamento": "TP02",
            "fiscal_mode_payment": "MP05",
            "date_add": "2026-07-01 10:00:00",
        }
        fatturapa_service.company_civic = ""
        xml_fr = fatturapa_service._generate_xml(
            order_fr, [line_vies], "00020", include_shipping=False
        )
        result_fr = validate_fatturapa_xml(xml_fr)
        assert result_fr["valid"] is True, result_fr["errors"]
