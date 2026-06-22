"""Unit test — codice natura FatturaPA (Natura vs RiferimentoNormativo)."""
import pytest

from src.services.external.fatturapa_natura import normalize_natura_code
from src.services.external.fatturapa_validator import FatturaPAValidator


class TestNormalizeNaturaCode:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("N3.1", "N3.1"),
            ("n3.2", "N3.2"),
            (" N6.9 ", "N6.9"),
            ("N7", "N7"),
            ("N1", "N1"),
        ],
    )
    def test_valid_codes(self, raw, expected):
        assert normalize_natura_code(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            None,
            "   ",
            "N3.1 - Non imponibili - esportazioni",
            "invalid",
            "N8",
            "E123",
        ],
    )
    def test_invalid_or_non_code_values(self, raw):
        assert normalize_natura_code(raw) is None


class TestFatturaPAValidatorNatura:
    def setup_method(self):
        self.validator = FatturaPAValidator()

    def test_accepts_subcodes(self):
        ok, msg = self.validator._validate_natura_iva("N3.1")
        assert ok is True
        assert msg is None

    def test_rejects_extended_label(self):
        ok, msg = self.validator._validate_natura_iva(
            "N3.1 - Non imponibili - esportazioni"
        )
        assert ok is False
        assert msg is not None
