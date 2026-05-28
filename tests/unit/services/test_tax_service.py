"""Unit test TaxService — set_country_default (BE-VIES-1)."""
import pytest

from src.core.exceptions import BusinessRuleException
from src.models.country import Country
from src.models.tax import Tax
from src.repository.tax_repository import TaxRepository
from src.services.routers.tax_service import TaxService


@pytest.fixture
def tax_service(db_session):
    return TaxService(TaxRepository(db_session))


@pytest.fixture
def it_country(db_session):
    country = Country(id_origin=1, name="Italy", iso_code="IT")
    db_session.add(country)
    db_session.commit()
    db_session.refresh(country)
    return country


@pytest.mark.asyncio
class TestTaxServiceSetCountryDefault:
    async def test_raises_when_tax_has_no_country(self, tax_service, db_session):
        tax = Tax(is_default=0, name="Orphan Tax", percentage=22, code="X")
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        with pytest.raises(BusinessRuleException):
            await tax_service.set_country_default(tax.id_tax)

    async def test_replaces_existing_default(self, tax_service, it_country, db_session):
        repo = TaxRepository(db_session)
        tax_a = repo.create(
            Tax(
                id_country=it_country.id_country,
                is_default=1,
                name="IVA IT 22%",
                percentage=22,
                code="A",
            )
        )
        tax_b = repo.create(
            Tax(
                id_country=it_country.id_country,
                is_default=0,
                name="IVA IT 10%",
                percentage=10,
                code="B",
            )
        )

        result = await tax_service.set_country_default(tax_b.id_tax)

        assert result.id_tax == tax_b.id_tax
        assert result.is_default == 1
        db_session.expire_all()
        assert repo.get_tax_by_id(tax_a.id_tax).is_default == 0
        assert repo.get_tax_by_id(tax_b.id_tax).is_default == 1

    async def test_invalid_iso_code_raises(self, tax_service):
        with pytest.raises(BusinessRuleException):
            await tax_service.get_default_by_country_iso("ITA")
