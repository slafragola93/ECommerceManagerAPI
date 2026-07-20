import pytest

from src.services.external.fatturapa_customer_address import (
    normalize_customer_vat,
    resolve_codice_destinatario,
    resolve_invoice_state,
    validate_customer_cap,
    validate_customer_provincia,
)


class TestFatturaPACustomerAddress:
    def test_normalize_customer_vat_italy_strips_prefix(self):
        assert normalize_customer_vat("IT08632861210", "IT") == "08632861210"

    def test_normalize_customer_vat_foreign_strips_country(self):
        assert normalize_customer_vat("DE123456789", "DE") == "123456789"

    def test_resolve_codice_destinatario_foreign(self):
        assert resolve_codice_destinatario("DE", "ABCDEFG") == "XXXXXXX"

    def test_resolve_codice_destinatario_italy_with_sdi(self):
        assert resolve_codice_destinatario("IT", "ABC1234") == "ABC1234"

    def test_resolve_codice_destinatario_italy_default(self):
        assert resolve_codice_destinatario("IT", None) == "0000000"

    def test_validate_customer_cap_italy(self):
        assert validate_customer_cap("20121", "IT") == "20121"

    def test_validate_customer_cap_foreign(self):
        assert validate_customer_cap("10115", "DE") == "10115"

    def test_validate_customer_cap_italy_invalid(self):
        with pytest.raises(ValueError, match="5 cifre"):
            validate_customer_cap("1011", "IT")

    def test_validate_customer_provincia_italy_required(self):
        with pytest.raises(ValueError, match="Provincia obbligatoria"):
            validate_customer_provincia("", "IT")

    def test_validate_customer_provincia_foreign_optional(self):
        assert validate_customer_provincia("", "DE") is None

    def test_validate_customer_provincia_foreign_value(self):
        assert validate_customer_provincia("Bayern", "DE") == "Bayern"

    def test_resolve_invoice_state_foreign_passthrough(self):
        assert resolve_invoice_state("Bayern", "DE") == "Bayern"
