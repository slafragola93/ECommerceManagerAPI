"""Unit test TaxRepository — country default helpers (BE-VIES-1)."""
import pytest

from src.models.country import Country
from src.models.tax import Tax
from src.repository.tax_repository import TaxRepository


@pytest.fixture
def tax_repo(db_session):
    return TaxRepository(db_session)


@pytest.fixture
def it_country(db_session):
    country = Country(id_origin=1, name="Italy", iso_code="IT")
    db_session.add(country)
    db_session.commit()
    db_session.refresh(country)
    return country


@pytest.fixture
def de_country(db_session):
    country = Country(id_origin=2, name="Germany", iso_code="DE")
    db_session.add(country)
    db_session.commit()
    db_session.refresh(country)
    return country


class TestTaxRepositoryCountryDefaults:
    def test_get_default_by_country_returns_default_tax(self, tax_repo, it_country):
        tax = Tax(
            id_country=it_country.id_country,
            is_default=1,
            name="IVA IT 22%",
            percentage=22,
            code="VATIT",
        )
        tax_repo.create(tax)

        result = tax_repo.get_default_by_country(it_country.id_country)
        assert result is not None
        assert result.id_tax == tax.id_tax
        assert result.is_default == 1

    def test_get_default_by_country_miss(self, tax_repo, it_country):
        assert tax_repo.get_default_by_country(it_country.id_country) is None

    def test_get_default_by_country_iso(self, tax_repo, de_country):
        tax = Tax(
            id_country=de_country.id_country,
            is_default=1,
            name="IVA DE 19%",
            percentage=19,
            code="VATDE",
        )
        tax_repo.create(tax)

        result = tax_repo.get_default_by_country_iso("de")
        assert result is not None
        assert result.percentage == 19

    def test_set_country_default_atomic_single_default(
        self, tax_repo, it_country, db_session
    ):
        tax_a = Tax(
            id_country=it_country.id_country,
            is_default=1,
            name="IVA IT 22%",
            percentage=22,
            code="A",
        )
        tax_b = Tax(
            id_country=it_country.id_country,
            is_default=0,
            name="IVA IT 10%",
            percentage=10,
            code="B",
        )
        tax_repo.create(tax_a)
        tax_repo.create(tax_b)

        updated = tax_repo.set_country_default_atomic(tax_b.id_tax, it_country.id_country)

        db_session.expire_all()
        assert updated.is_default == 1
        refreshed_a = tax_repo.get_tax_by_id(tax_a.id_tax)
        refreshed_b = tax_repo.get_tax_by_id(tax_b.id_tax)
        assert refreshed_a.is_default == 0
        assert refreshed_b.is_default == 1

    def test_list_country_defaults(self, tax_repo, it_country, de_country):
        tax_repo.create(
            Tax(
                id_country=it_country.id_country,
                is_default=1,
                name="IVA IT 22%",
                percentage=22,
                code="IT",
            )
        )
        tax_repo.create(
            Tax(
                id_country=de_country.id_country,
                is_default=1,
                name="IVA DE 19%",
                percentage=19,
                code="DE",
            )
        )
        tax_repo.create(
            Tax(
                id_country=it_country.id_country,
                is_default=0,
                name="IVA IT 10%",
                percentage=10,
                code="IT10",
            )
        )

        defaults = tax_repo.list_country_defaults()
        assert len(defaults) == 2
        country_ids = {t.id_country for t in defaults}
        assert country_ids == {it_country.id_country, de_country.id_country}
