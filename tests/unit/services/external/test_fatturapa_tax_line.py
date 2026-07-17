"""Unit test — risoluzione tax/VIES e DatiRiepilogo multi-aliquota FatturaPA."""
import xml.etree.ElementTree as ET

import pytest

from src.models.tax import Tax
from src.services.external.fatturapa_tax_line import (
    VIES_NATURA_CODE,
    VIES_DEFAULT_NORMATIVO,
    build_riepilogo_groups,
    enrich_line_item_tax_fields,
    resolve_line_tax,
    vies_eligible_from_order_data,
)


class TestResolveLineTax:
    def test_vies_eligible_product_forces_n3_2_and_zero(self):
        tax = Tax(percentage=22, electronic_code="", note="")
        result = resolve_line_tax(tax, vies_eligible=True, is_product_line=True)
        assert result.aliquota == 0
        assert result.natura == VIES_NATURA_CODE
        assert result.riferimento_normativo == VIES_DEFAULT_NORMATIVO

    def test_vies_eligible_product_keeps_tax_electronic_code(self):
        tax = Tax(percentage=0, electronic_code="N3.2", note="Custom normativo")
        result = resolve_line_tax(tax, vies_eligible=True, is_product_line=True)
        assert result.aliquota == 0
        assert result.natura == "N3.2"
        assert result.riferimento_normativo == "Custom normativo"

    def test_non_vies_ordinary_22_no_natura(self):
        tax = Tax(percentage=22, electronic_code="", note="")
        result = resolve_line_tax(tax, vies_eligible=False, is_product_line=True)
        assert result.aliquota == 22
        assert result.natura is None

    def test_zero_percent_without_vies_uses_electronic_code(self):
        tax = Tax(percentage=0, electronic_code="N3.1", note="Export")
        result = resolve_line_tax(tax, vies_eligible=False, is_product_line=True)
        assert result.aliquota == 0
        assert result.natura == "N3.1"
        assert result.riferimento_normativo == "Export"

    def test_shipping_not_forced_vies_on_eligible_order(self):
        tax = Tax(percentage=22, electronic_code="", note="")
        result = resolve_line_tax(tax, vies_eligible=True, is_product_line=False)
        assert result.aliquota == 22
        assert result.natura is None


class TestBuildRiepilogoGroups:
    def test_single_aliquota_group(self):
        lines = [
            {
                "line_net_total": 100.0,
                "tax_percentage": 22.0,
                "tax_nature": None,
                "tax_note": None,
            }
        ]
        groups = build_riepilogo_groups(lines)
        assert len(groups) == 1
        assert groups[0]["AliquotaIVA"] == 22.0
        assert groups[0]["ImponibileImporto"] == 100.0
        assert groups[0]["Imposta"] == 22.0

    def test_vies_products_plus_shipping_two_groups(self):
        lines = [
            {
                "line_net_total": 200.0,
                "tax_percentage": 0.0,
                "tax_nature": "N3.2",
                "tax_note": VIES_DEFAULT_NORMATIVO,
            },
            {
                "line_net_total": 10.0,
                "tax_percentage": 22.0,
                "tax_nature": None,
                "tax_note": None,
            },
        ]
        groups = build_riepilogo_groups(lines)
        assert len(groups) == 2
        vies_group = next(g for g in groups if g["AliquotaIVA"] == 0.0)
        ship_group = next(g for g in groups if g["AliquotaIVA"] == 22.0)
        assert vies_group["Natura"] == "N3.2"
        assert vies_group["Imposta"] == 0.0
        assert ship_group["Imposta"] == 2.2


class TestViesEligibleFromOrderData:
    @pytest.mark.parametrize(
        "status,expected",
        [
            ("eligible", True),
            ("ELIGIBLE", True),
            ("not_eligible", False),
            (None, False),
        ],
    )
    def test_vies_status_parsing(self, status, expected):
        assert vies_eligible_from_order_data({"vies_status": status}) is expected


class TestGenerateXmlViesIntegration:
    """Verifica output XML _generate_xml con righe arricchite."""

    @pytest.fixture
    def fatturapa_service(self, db_session):
        from src.services.external.fatturapa_service import FatturaPAService

        service = FatturaPAService(db_session)
        service.vat_number = "12345678901"
        service.company_name = "Test Srl"
        service.company_address = "Via Roma"
        service.company_civic = "1"
        service.company_cap = "20100"
        service.company_city = "Milano"
        service.company_province = "MI"
        service.company_phone = "02123456"
        service.company_email = "test@example.com"
        service.company_contact = "Admin"
        service.company_iban = "IT60X0542811101000000123456"
        service.company_bank_name = "Banca Test"
        return service

    def test_vies_eligible_xml_contains_n3_2_and_zero_aliquota(
        self, fatturapa_service
    ):
        order_data = {
            "invoice_firstname": "Mario",
            "invoice_lastname": "Rossi",
            "invoice_company": "",
            "customer_fiscal_code": "RSSMRA80A01F205X",
            "invoice_pec": "",
            "invoice_sdi": "0000000",
            "invoice_vat": "IT12345678901",
            "invoice_address1": "Via Test 1",
            "invoice_postcode": "20100",
            "invoice_city": "Milano",
            "invoice_state": "MI",
            "country_iso": "IT",
            "tipo_documento_fe": "TD01",
            "total_price": 210.0,
            "total_discounts": 0,
            "shipping_price_tax_excl": 10.0,
            "shipping_tax_percentage": 22.0,
            "shipping_id_tax": None,
            "vies_status": "eligible",
            "condizioni_pagamento": "TP02",
            "fiscal_mode_payment": "MP05",
            "date_add": "2026-07-01 10:00:00",
        }
        line = enrich_line_item_tax_fields(
            {
                "product_name": "Prodotto UE",
                "product_qty": 2,
                "product_price": 100.0,
                "reduction_percent": 0,
                "reduction_amount": 0,
                "id_tax": 1,
            },
            resolve_line_tax(
                Tax(percentage=0, electronic_code="N3.2", note=VIES_DEFAULT_NORMATIVO),
                vies_eligible=True,
                is_product_line=True,
            ),
        )

        xml = fatturapa_service._generate_xml(
            order_data, [line], "00001", include_shipping=True
        )

        root = ET.fromstring(xml)
        riepilogo_blocks = [el for el in root.iter("DatiRiepilogo")]
        aliquote = [el.text for el in root.iter("AliquotaIVA")]
        nature_values = [el.text for el in root.iter("Natura") if el.text]

        assert "N3.2" in nature_values
        assert "0.00" in aliquote
        assert "22.00" in aliquote
        assert len(riepilogo_blocks) == 2
