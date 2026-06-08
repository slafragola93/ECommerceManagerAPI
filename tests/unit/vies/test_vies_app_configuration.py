"""Unit test — helper VIES su app_configurations."""
from src.models.app_configuration import AppConfiguration
from src.vies.vies_app_configuration import (
    REVERSE_CHARGE_CONFIG_NAME,
    VIES_CONFIG_CATEGORY,
    get_reverse_charge_id_tax,
    parse_reverse_charge_id_tax,
    set_reverse_charge_id_tax,
)


class TestViesAppConfiguration:
    def test_parse_reverse_charge(self):
        assert parse_reverse_charge_id_tax("5") == 5
        assert parse_reverse_charge_id_tax("") is None
        assert parse_reverse_charge_id_tax(None) is None

    def test_set_and_get(self, db_session):
        assert set_reverse_charge_id_tax(db_session, 42) == 42
        assert get_reverse_charge_id_tax(db_session) == 42

        set_reverse_charge_id_tax(db_session, None)
        assert get_reverse_charge_id_tax(db_session) is None

        row = (
            db_session.query(AppConfiguration)
            .filter_by(category=VIES_CONFIG_CATEGORY, name=REVERSE_CHARGE_CONFIG_NAME)
            .first()
        )
        assert row.value is None
