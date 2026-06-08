"""Unit test — get_vies_exemption_tax_id / resolve_vies_exemption_tax_id_with_fallback."""
from src.models.app_configuration import AppConfiguration
from src.models.tax import Tax
from src.vies.tax_resolution import (
    get_vies_exemption_tax_id,
    is_vies_eligible_status,
    resolve_vies_exemption_tax_id_with_fallback,
)
from src.models.order import ViesStatus


class TestIsViesEligibleStatus:
    def test_eligible_enum_and_string(self):
        assert is_vies_eligible_status(ViesStatus.ELIGIBLE) is True
        assert is_vies_eligible_status("eligible") is True
        assert is_vies_eligible_status(ViesStatus.NOT_ELIGIBLE) is False
        assert is_vies_eligible_status(None) is False


class TestViesExemptionTaxId:
    def test_reverse_charge_from_settings(self, db_session):
        rc = Tax(name="RC 0%", percentage=0, code="RC0", is_default=0)
        db_session.add(rc)
        db_session.commit()
        db_session.add(
            AppConfiguration(
                id_lang=0,
                category="vies",
                name="reverse_charge_id_tax",
                value=str(rc.id_tax),
                description="test",
                is_encrypted=False,
            )
        )
        db_session.commit()
        assert get_vies_exemption_tax_id(db_session) == rc.id_tax
        assert resolve_vies_exemption_tax_id_with_fallback(db_session) == rc.id_tax

    def test_fallback_first_zero_percent(self, db_session):
        zero = Tax(name="Zero", percentage=0, code="Z0", is_default=0)
        db_session.add(zero)
        db_session.commit()
        assert resolve_vies_exemption_tax_id_with_fallback(db_session) == zero.id_tax
