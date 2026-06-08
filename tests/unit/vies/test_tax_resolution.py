"""Unit test — resolve_tax_id_for_delivery."""
import pytest

from src.models.app_configuration import AppConfiguration
from src.models.country import Country
from src.models.order import ViesStatus
from src.models.tax import Tax
from src.vies.tax_resolution import resolve_tax_id_for_delivery
from src.vies.vies_app_configuration import (
    REVERSE_CHARGE_CONFIG_NAME,
    VIES_CONFIG_CATEGORY,
)


@pytest.fixture
def fr_country(db_session):
    c = Country(id_origin=1, name="France", iso_code="FR")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def taxes_setup(db_session, fr_country):
    fr_default = Tax(
        id_country=fr_country.id_country,
        is_default=1,
        name="IVA FR 20%",
        percentage=20,
        code="FR20",
    )
    global_default = Tax(
        id_country=None,
        is_default=1,
        name="IVA IT fallback 22%",
        percentage=22,
        code="IT22",
    )
    zero = Tax(name="IVA 0%", percentage=0, code="Z0", is_default=0)
    db_session.add_all([fr_default, global_default, zero])
    db_session.commit()
    for t in (fr_default, global_default, zero):
        db_session.refresh(t)
    db_session.add(
        AppConfiguration(
            id_lang=0,
            category=VIES_CONFIG_CATEGORY,
            name=REVERSE_CHARGE_CONFIG_NAME,
            value=str(zero.id_tax),
            description="test",
            is_encrypted=False,
        )
    )
    db_session.commit()
    return fr_default, global_default, zero


class TestTaxResolution:
    def test_eligible_uses_reverse_charge(self, db_session, taxes_setup, fr_country):
        _, _, zero = taxes_setup
        assert (
            resolve_tax_id_for_delivery(
                db_session, fr_country.id_country, ViesStatus.ELIGIBLE
            )
            == zero.id_tax
        )

    def test_not_eligible_uses_country_default(
        self, db_session, taxes_setup, fr_country
    ):
        fr_default, _, _ = taxes_setup
        assert (
            resolve_tax_id_for_delivery(
                db_session, fr_country.id_country, ViesStatus.NOT_ELIGIBLE
            )
            == fr_default.id_tax
        )

    def test_no_country_default_uses_global(
        self, db_session, taxes_setup
    ):
        _, global_default, _ = taxes_setup
        assert (
            resolve_tax_id_for_delivery(db_session, 999, ViesStatus.NOT_ELIGIBLE)
            == global_default.id_tax
        )
