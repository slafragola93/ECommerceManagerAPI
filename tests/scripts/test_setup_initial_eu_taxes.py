"""Test idempotenza seed UE (BE-VIES-1) — funzione in src.vies.eu_vat_seed."""
import pytest

from src.models.country import Country
from src.models.tax import Tax
from src.vies.eu_vat_seed import setup_eu_country_taxes


@pytest.fixture
def eu_countries_sample(db_session):
    """Tre paesi UE minimi per verificare idempotenza seed."""
    codes = [("IT", "Italy", 22), ("DE", "Germany", 19), ("FR", "France", 20)]
    created = []
    for iso, name, _ in codes:
        c = Country(id_origin=len(created) + 1, name=name, iso_code=iso)
        db_session.add(c)
        created.append(c)
    db_session.commit()
    for c in created:
        db_session.refresh(c)
    return created


def test_setup_eu_country_taxes_idempotent(db_session, eu_countries_sample, capsys):
    setup_eu_country_taxes(db_session)
    count_after_first = db_session.query(Tax).filter(Tax.is_default == 1).count()

    setup_eu_country_taxes(db_session)
    count_after_second = db_session.query(Tax).filter(Tax.is_default == 1).count()

    assert count_after_first == count_after_second
    assert count_after_first >= len(eu_countries_sample)

    it_tax = (
        db_session.query(Tax)
        .join(Country, Tax.id_country == Country.id_country)
        .filter(Country.iso_code == "IT", Tax.is_default == 1)
        .first()
    )
    assert it_tax is not None
    assert it_tax.percentage == 22
