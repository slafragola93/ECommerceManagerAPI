"""Unit test — DatiFattureCollegate obbligatorio per TD04."""
from src.services.external.fatturapa_validator import FatturaPAValidator


def _company_data():
    return {
        "vat_number": "08632861210",
        "fiscal_code": "08632861210",
        "company_name": "Test Srl",
        "address": "Via Roma",
        "civic_number": "1",
        "postal_code": "20100",
        "city": "Milano",
        "province": "MI",
        "phone": "0212345678",
        "email": "test@example.com",
        "account_holder": "Admin",
        "tax_regime": "RF01",
    }


def _order_data_td04(**overrides):
    data = {
        "tipo_documento_fe": "TD04",
        "document_number": "00021",
        "document_date": "2026-07-15",
        "invoice_firstname": "Mario",
        "invoice_lastname": "Rossi",
        "invoice_company": "",
        "customer_fiscal_code": "RSSMRA80A01F205X",
        "invoice_address1": "Via Test 1",
        "invoice_postcode": "20100",
        "invoice_city": "Milano",
        "invoice_state": "MI",
        "country_iso": "IT",
        "invoice_sdi": "0000000",
        "invoice_vat": "",
        "id_fiscal_document_ref": 99,
        "linked_invoice_number": "00020",
        "linked_invoice_date": "2026-07-10",
    }
    data.update(overrides)
    return data


class TestValidatorDatiFattureCollegate:
    def test_td04_with_linked_invoice_ok(self):
        result = FatturaPAValidator().validate(
            _order_data_td04(), [], _company_data()
        )
        collegate_errors = [
            e
            for e in result["errors"]
            if e.get("rule") == "dati_fatture_collegate_td04"
        ]
        assert collegate_errors == []

    def test_td04_without_linked_invoice_fails(self):
        result = FatturaPAValidator().validate(
            _order_data_td04(
                linked_invoice_number=None, linked_invoice_date=None
            ),
            [],
            _company_data(),
        )
        assert result["valid"] is False
        assert any(
            e.get("rule") == "dati_fatture_collegate_td04" for e in result["errors"]
        )

    def test_td01_skips_collegate_check(self):
        result = FatturaPAValidator().validate(
            _order_data_td04(
                tipo_documento_fe="TD01",
                linked_invoice_number=None,
                linked_invoice_date=None,
                id_fiscal_document_ref=None,
            ),
            [],
            _company_data(),
        )
        assert not any(
            e.get("rule") == "dati_fatture_collegate_td04" for e in result["errors"]
        )
