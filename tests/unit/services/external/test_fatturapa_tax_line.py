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


class TestGenerateXmlSedeStructure:
    """Regressione Gap Sede: NumeroCivico vuoto, Provincia estera, CAP AdE."""

    @pytest.fixture
    def fatturapa_service(self, db_session):
        from src.services.external.fatturapa_service import FatturaPAService

        service = FatturaPAService(db_session)
        service.vat_number = "08632861210"
        service.company_name = "Test Srl"
        service.company_address = "Via Roma"
        service.company_civic = ""  # Gap 1: non deve produrre <NumeroCivico />
        service.company_cap = "20100"
        service.company_city = "Milano"
        service.company_province = "MI"
        service.company_phone = "02123456"
        service.company_email = "test@example.com"
        service.company_contact = "Admin"
        service.company_iban = "IT60X0542811101000000123456"
        service.company_bank_name = "Banca Test"
        return service

    def _base_line(self):
        from src.models.tax import Tax
        from src.services.external.fatturapa_tax_line import (
            enrich_line_item_tax_fields,
            resolve_line_tax,
        )

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

    def test_italy_cliente_has_provincia_and_no_empty_civico(self, fatturapa_service):
        order_data = {
            "invoice_firstname": "Mario",
            "invoice_lastname": "Rossi",
            "invoice_company": "Cliente Spa",
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
            "total_price": 122.0,
            "total_discounts": 0,
            "shipping_price_tax_excl": 0,
            "condizioni_pagamento": "TP02",
            "fiscal_mode_payment": "MP05",
            "date_add": "2026-07-01 10:00:00",
        }
        xml = fatturapa_service._generate_xml(
            order_data, [self._base_line()], "00001", include_shipping=False
        )
        assert "<NumeroCivico />" not in xml
        assert "<NumeroCivico></NumeroCivico>" not in xml

        root = ET.fromstring(xml)
        sedi = list(root.iter("Sede"))
        assert len(sedi) == 2
        cedente_sede, cessionario_sede = sedi
        assert cedente_sede.find("NumeroCivico") is None
        assert cedente_sede.find("Provincia").text == "MI"
        assert cessionario_sede.find("Provincia").text == "MI"
        assert cessionario_sede.find("CAP").text == "20100"
        assert cessionario_sede.find("Nazione").text == "IT"

    def test_france_cliente_no_provincia_cap_00000_no_empty_civico(
        self, fatturapa_service
    ):
        """Regressione IT08632861210_000020.xml (L'Oreal / Francia)."""
        order_data = {
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
            "total_price": 122.0,
            "total_discounts": 0,
            "shipping_price_tax_excl": 0,
            "vies_status": "eligible",
            "condizioni_pagamento": "TP02",
            "fiscal_mode_payment": "MP05",
            "date_add": "2026-07-01 10:00:00",
        }
        xml = fatturapa_service._generate_xml(
            order_data, [self._base_line()], "00020", include_shipping=False
        )
        assert "<NumeroCivico />" not in xml
        assert "<NumeroCivico></NumeroCivico>" not in xml

        root = ET.fromstring(xml)
        sedi = list(root.iter("Sede"))
        assert len(sedi) == 2
        cedente_sede, cessionario_sede = sedi

        assert cedente_sede.find("NumeroCivico") is None
        assert cedente_sede.find("Nazione").text == "IT"
        assert cedente_sede.find("Provincia").text == "MI"

        assert cessionario_sede.find("Provincia") is None
        assert cessionario_sede.find("CAP").text == "00000"
        assert cessionario_sede.find("Nazione").text == "FR"
        assert "75002" in (cessionario_sede.find("Indirizzo").text or "")


class TestGenerateXmlCedenteAndDocumentDate:
    """CF cedente = azienda; Data = document_date fiscale."""

    @pytest.fixture
    def fatturapa_service(self, db_session):
        from src.services.external.fatturapa_service import FatturaPAService

        service = FatturaPAService(db_session)
        service.vat_number = "08632861210"
        service.company_fiscal_code = "08632861210"
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

    def _base_line(self):
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

    def test_cedente_cf_is_company_not_customer(self, fatturapa_service):
        customer_cf = "RSSMRA80A01F205X"
        order_data = {
            "invoice_firstname": "Mario",
            "invoice_lastname": "Rossi",
            "invoice_company": "",
            "customer_fiscal_code": customer_cf,
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
            order_data, [self._base_line()], "00001", include_shipping=False
        )
        root = ET.fromstring(xml)
        cedente = next(root.iter("CedentePrestatore"))
        cessionario = next(root.iter("CessionarioCommittente"))
        cedente_cf = cedente.find("DatiAnagrafici/CodiceFiscale")
        cessionario_cf = cessionario.find("DatiAnagrafici/CodiceFiscale")
        assert cedente_cf is not None
        assert cedente_cf.text == "08632861210"
        assert cedente_cf.text != customer_cf
        assert cessionario_cf is not None
        assert cessionario_cf.text == customer_cf

        data_el = next(root.iter("Data"))
        assert data_el.text == "2026-07-10"


class TestGenerateXmlDatiFattureCollegateTd04:
    """BE-PA-P0-06: TD04 deve riferire la fattura originale."""

    @pytest.fixture
    def fatturapa_service(self, db_session):
        from src.services.external.fatturapa_service import FatturaPAService

        service = FatturaPAService(db_session)
        service.vat_number = "08632861210"
        service.company_fiscal_code = "08632861210"
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

    def _base_line(self):
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

    def _order_data_td04(self, **overrides):
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
            "tipo_documento_fe": "TD04",
            "total_price": 122.0,
            "total_discounts": 0,
            "shipping_price_tax_excl": 0,
            "document_date": "2026-07-15",
            "linked_invoice_number": "00020",
            "linked_invoice_date": "2026-07-10",
            "id_fiscal_document_ref": 99,
            "condizioni_pagamento": "TP02",
            "fiscal_mode_payment": "MP05",
            "date_add": "2026-07-01 10:00:00",
        }
        data.update(overrides)
        return data

    def test_td04_emits_dati_fatture_collegate(self, fatturapa_service):
        xml = fatturapa_service._generate_xml(
            self._order_data_td04(),
            [self._base_line()],
            "00021",
            include_shipping=False,
        )
        root = ET.fromstring(xml)
        assert next(root.iter("TipoDocumento")).text == "TD04"
        collegate = next(root.iter("DatiFattureCollegate"))
        assert collegate.find("IdDocumento").text == "20"
        assert collegate.find("Data").text == "2026-07-10"

    def test_td04_without_linked_invoice_raises(self, fatturapa_service):
        with pytest.raises(ValueError, match="fattura di riferimento"):
            fatturapa_service._generate_xml(
                self._order_data_td04(
                    linked_invoice_number=None, linked_invoice_date=None
                ),
                [self._base_line()],
                "00021",
                include_shipping=False,
            )

    def test_td01_does_not_emit_dati_fatture_collegate(self, fatturapa_service):
        order = self._order_data_td04(tipo_documento_fe="TD01")
        order.pop("linked_invoice_number", None)
        order.pop("linked_invoice_date", None)
        xml = fatturapa_service._generate_xml(
            order, [self._base_line()], "00020", include_shipping=False
        )
        root = ET.fromstring(xml)
        assert list(root.iter("DatiFattureCollegate")) == []
