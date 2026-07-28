import xml.etree.ElementTree as ET

import pytest

from src.services.external.fatturapa_customer_address import (
    FOREIGN_CAP_PLACEHOLDER,
    build_sede_fields,
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

    def test_validate_customer_cap_foreign_always_00000(self):
        assert validate_customer_cap("75002", "FR") == FOREIGN_CAP_PLACEHOLDER
        assert validate_customer_cap("10115", "DE") == FOREIGN_CAP_PLACEHOLDER
        assert validate_customer_cap("", "FR") == FOREIGN_CAP_PLACEHOLDER

    def test_validate_customer_cap_italy_invalid(self):
        with pytest.raises(ValueError, match="5 cifre"):
            validate_customer_cap("1011", "IT")

    def test_validate_customer_provincia_italy_required(self):
        with pytest.raises(ValueError, match="Provincia obbligatoria"):
            validate_customer_provincia("", "IT")

    def test_validate_customer_provincia_foreign_always_none(self):
        assert validate_customer_provincia("", "DE") is None
        assert validate_customer_provincia("Paris", "FR") is None
        assert validate_customer_provincia("Bayern", "DE") is None

    def test_validate_customer_provincia_italy_ok(self):
        assert validate_customer_provincia("MI", "IT") == "MI"

    def test_resolve_invoice_state_foreign_none(self):
        assert resolve_invoice_state("Bayern", "DE") is None
        assert resolve_invoice_state("Paris", "FR") is None


class TestBuildSedeFields:
    def test_italy_with_civico_and_provincia(self):
        fields = build_sede_fields(
            indirizzo="Via Roma",
            nazione="IT",
            comune="Milano",
            cap="20100",
            numero_civico="12",
            provincia="MI",
        )
        assert fields["Indirizzo"] == "Via Roma"
        assert fields["NumeroCivico"] == "12"
        assert fields["CAP"] == "20100"
        assert fields["Comune"] == "Milano"
        assert fields["Provincia"] == "MI"
        assert fields["Nazione"] == "IT"

    def test_italy_omits_empty_numero_civico(self):
        fields = build_sede_fields(
            indirizzo="Via Roma",
            nazione="IT",
            comune="Milano",
            cap="20100",
            numero_civico="",
            provincia="MI",
        )
        assert "NumeroCivico" not in fields
        assert fields["Provincia"] == "MI"

    def test_france_omits_provincia_uses_ade_cap(self):
        fields = build_sede_fields(
            indirizzo="41 Rue Martre",
            nazione="FR",
            comune="Clichy",
            cap="75002",
            numero_civico="",
            provincia="Paris",
        )
        assert "Provincia" not in fields
        assert "NumeroCivico" not in fields
        assert fields["CAP"] == FOREIGN_CAP_PLACEHOLDER
        assert fields["Nazione"] == "FR"
        assert "75002" in fields["Indirizzo"]
        assert fields["Indirizzo"].startswith("41 Rue Martre")

    def test_france_does_not_duplicate_cap_in_indirizzo(self):
        fields = build_sede_fields(
            indirizzo="41 Rue Martre 75002",
            nazione="FR",
            comune="Clichy",
            cap="75002",
            provincia="Paris",
        )
        assert fields["Indirizzo"] == "41 Rue Martre 75002"
        assert fields["CAP"] == FOREIGN_CAP_PLACEHOLDER
