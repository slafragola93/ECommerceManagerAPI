"""Regressione XML FatturaPA: TD04/TD01 pagamento, PEC, IBAN, CF, Arrotondamento."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

import pytest

from src.models.tax import Tax
from src.services.external.fatturapa_filename import resolve_fatturapa_filename_from_xml
from src.services.external.fatturapa_service import (
    PAYMENT_MODES_REQUIRING_IBAN,
    FatturaPAService,
)
from src.services.external.fatturapa_tax_line import (
    enrich_line_item_tax_fields,
    resolve_line_tax,
)


@pytest.fixture
def fatturapa_service():
    svc = FatturaPAService.__new__(FatturaPAService)
    svc.db = MagicMock()
    svc.vat_number = "IT08632861210"
    svc.company_fiscal_code = "ABCDEF12G34H567I"  # non deve finire nell'XML cedente
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
    svc._config = {}

    def _get(category, name, default=None):
        return svc._config.get(f"{category}.{name}", default)

    svc._get_config_value = _get
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


def _base_order(**overrides):
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
        "total_discounts": 0,
        "shipping_price_tax_excl": 0,
        "document_date": "2026-07-22",
        "condizioni_pagamento": "TP02",
        "fiscal_mode_payment": "MP05",
        "date_add": "2026-04-01 10:00:00",
        "payment_due_date": "2026-05-01",
    }
    data.update(overrides)
    return data


class TestNcXmlPaymentDueDate:
    def test_td04_omits_data_scadenza_by_default(self, fatturapa_service):
        """Regressione stile NC 000003: Data NC > data fattura collegata → no scadenza."""
        order = _base_order(
            tipo_documento_fe="TD04",
            document_date="2026-07-22",
            linked_invoice_number="000003",
            linked_invoice_date="2026-04-17",
            payment_due_date="2026-05-17",
            date_add="2026-04-17 10:00:00",
        )
        xml = fatturapa_service._generate_xml(
            order, [_line_22()], "000003", include_shipping=False
        )
        root = ET.fromstring(xml)
        assert root.find(".//DataScadenzaPagamento") is None
        assert root.find(".//DatiFattureCollegate/IdDocumento").text == "3"
        assert root.find(".//DatiFattureCollegate/Data").text == "2026-04-17"

    def test_td04_includes_scadenza_when_flag_true(self, fatturapa_service):
        fatturapa_service._config[
            "electronic_invoicing.td04_include_payment_due_date"
        ] = "true"
        order = _base_order(
            tipo_documento_fe="TD04",
            document_date="2026-07-22",
            linked_invoice_number="20",
            linked_invoice_date="2026-04-17",
            payment_due_date="2026-05-17",
        )
        xml = fatturapa_service._generate_xml(
            order, [_line_22()], "000021", include_shipping=False
        )
        scad = ET.fromstring(xml).find(".//DataScadenzaPagamento")
        assert scad is not None
        assert scad.text == "2026-08-21"  # document_date + 30 (due < Data NC)

    def test_td01_scadenza_from_document_date_not_order_date(self, fatturapa_service):
        order = _base_order(
            tipo_documento_fe="TD01",
            document_date="2026-07-22",
            date_add="2020-01-01 10:00:00",
            payment_due_date=None,
        )
        xml = fatturapa_service._generate_xml(
            order, [_line_22()], "000010", include_shipping=False
        )
        scad = ET.fromstring(xml).find(".//DataScadenzaPagamento")
        assert scad is not None
        assert scad.text == "2026-08-21"


class TestNcXmlPecIbanCfArrotondamento:
    def test_pec_emitted_with_codice_0000000(self, fatturapa_service):
        order = _base_order(invoice_pec="cliente@pec.it", invoice_sdi="0000000")
        xml = fatturapa_service._generate_xml(
            order, [_line_22()], "000011", include_shipping=False
        )
        root = ET.fromstring(xml)
        assert root.find(".//CodiceDestinatario").text == "0000000"
        assert root.find(".//PECDestinatario").text == "cliente@pec.it"

    def test_mp08_omits_iban_and_istituto(self, fatturapa_service):
        assert "MP05" in PAYMENT_MODES_REQUIRING_IBAN
        order = _base_order(fiscal_mode_payment="MP08")
        xml = fatturapa_service._generate_xml(
            order, [_line_22()], "000012", include_shipping=False
        )
        root = ET.fromstring(xml)
        assert root.find(".//IBAN") is None
        assert root.find(".//IstitutoFinanziario") is None
        assert root.find(".//ModalitaPagamento").text == "MP08"

    def test_mp05_includes_iban(self, fatturapa_service):
        order = _base_order(fiscal_mode_payment="MP05")
        xml = fatturapa_service._generate_xml(
            order, [_line_22()], "000013", include_shipping=False
        )
        root = ET.fromstring(xml)
        assert root.find(".//IBAN").text == fatturapa_service.company_iban
        assert root.find(".//IstitutoFinanziario").text == "Banca Test"

    def test_cedente_cf_equals_id_codice_piva(self, fatturapa_service):
        order = _base_order()
        xml = fatturapa_service._generate_xml(
            order, [_line_22()], "000014", include_shipping=False
        )
        root = ET.fromstring(xml)
        id_codice = root.find(
            ".//CedentePrestatore/DatiAnagrafici/IdFiscaleIVA/IdCodice"
        ).text
        cf = root.find(".//CedentePrestatore/DatiAnagrafici/CodiceFiscale").text
        assert id_codice == "08632861210"
        assert cf == id_codice
        assert cf != fatturapa_service.company_fiscal_code

    def test_arrotondamento_always_present(self, fatturapa_service):
        order = _base_order()
        xml = fatturapa_service._generate_xml(
            order, [_line_22()], "000015", include_shipping=False
        )
        arrot = ET.fromstring(xml).find(".//Arrotondamento")
        assert arrot is not None
        assert arrot.text == "0.00"

    def test_filename_without_double_it_prefix(self, fatturapa_service):
        order = _base_order()
        xml = fatturapa_service._generate_xml(
            order, [_line_22()], "000016", include_shipping=False
        )
        filename = resolve_fatturapa_filename_from_xml(xml)
        assert filename == "IT08632861210_000016.xml"
        assert "ITIT" not in filename


class TestNcXmlTotalDiscounts:
    def test_td04_skips_order_buoni_sconto(self, fatturapa_service):
        order = _base_order(
            tipo_documento_fe="TD04",
            total_discounts=12.20,
            linked_invoice_number="20",
            linked_invoice_date="2026-04-17",
        )
        xml = fatturapa_service._generate_xml(
            order, [_line_22()], "000030", include_shipping=False
        )
        root = ET.fromstring(xml)
        descriptions = [el.text for el in root.iter("Descrizione")]
        assert "Buoni Sconto" not in descriptions
        assert root.find(".//Arrotondamento").text == "0.00"

    def test_td01_still_emits_buoni_sconto(self, fatturapa_service):
        order = _base_order(tipo_documento_fe="TD01", total_discounts=12.20)
        xml = fatturapa_service._generate_xml(
            order, [_line_22()], "000031", include_shipping=False
        )
        descriptions = [el.text for el in ET.fromstring(xml).iter("Descrizione")]
        assert "Buoni Sconto" in descriptions
