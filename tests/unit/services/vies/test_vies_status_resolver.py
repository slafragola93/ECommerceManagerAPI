"""Unit test — risoluzione vies_status (BE-VIES-2)."""
import pytest

from src.models.order import ViesStatus
from src.services.vies.vies_status_resolver import (
    extract_prestashop_vies_valid,
    has_invoice_vat_number,
    resolve_vies_status,
)


class TestHasInvoiceVatNumber:
    def test_empty(self):
        assert has_invoice_vat_number("") is False
        assert has_invoice_vat_number(None) is False

    def test_valid_vat(self):
        assert has_invoice_vat_number("DE123456789") is True
        assert has_invoice_vat_number("IT 08632861210") is True


class TestExtractPrestashopViesValid:
    def test_vies_valid_field(self):
        assert extract_prestashop_vies_valid({"vies_valid": 1}) is True
        assert extract_prestashop_vies_valid({"vies_valid": 0}) is False

    def test_vat_number_valid_alias(self):
        assert extract_prestashop_vies_valid({"vat_number_valid": "1"}) is True

    def test_vies_status_string(self):
        assert extract_prestashop_vies_valid({"vies_status": "eligible"}) is True
        assert extract_prestashop_vies_valid({"vies_status": "not_eligible"}) is False

    def test_missing_returns_none(self):
        assert extract_prestashop_vies_valid({}) is None


class TestResolveViesStatus:
    def test_italy_always_null(self):
        assert resolve_vies_status("IT", True, "DE123456789", True) is None

    def test_no_invoice_null(self):
        assert resolve_vies_status("DE", False, "DE123456789", True) is None

    def test_no_vat_null(self):
        assert resolve_vies_status("DE", True, "", True) is None

    def test_eligible(self):
        result = resolve_vies_status("DE", True, "DE123456789", True)
        assert result == ViesStatus.ELIGIBLE

    def test_not_eligible(self):
        result = resolve_vies_status("FR", True, "FR12345678901", False)
        assert result == ViesStatus.NOT_ELIGIBLE

    def test_unknown_vies_result_null(self):
        assert resolve_vies_status("ES", True, "ES12345678Z", None) is None
