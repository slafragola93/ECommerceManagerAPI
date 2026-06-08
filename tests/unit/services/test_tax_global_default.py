"""Unit test — default IVA globale (BE-VIES-FALLBACK-GLOBAL)."""
import pytest

from src.models.country import Country
from src.models.tax import Tax
from src.repository.tax_repository import TaxRepository
from src.schemas.tax_schema import TaxSchema
from src.services.routers.tax_service import TaxService


@pytest.fixture
def tax_service(db_session):
    return TaxService(TaxRepository(db_session))


@pytest.mark.asyncio
class TestTaxGlobalDefault:
    async def test_create_tax_with_null_country(self, tax_service, db_session):
        created = await tax_service.create_tax(
            TaxSchema(
                id_country=None,
                is_default=0,
                name="IVA Globale 22%",
                percentage=22,
                code="GLB22",
            )
        )
        assert created.id_country is None

    async def test_set_global_default_on_tax_without_country(
        self, tax_service, db_session
    ):
        tax = Tax(is_default=0, name="Fallback 22%", percentage=22, code="FB")
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        result = await tax_service.set_country_default(tax.id_tax)

        assert result.is_default == 1
        assert result.id_country is None
        others = (
            db_session.query(Tax)
            .filter(Tax.id_country.is_(None), Tax.is_default == 1)
            .all()
        )
        assert len(others) == 1

    async def test_only_one_global_default(self, tax_service, db_session):
        a = Tax(is_default=1, name="Global A", percentage=22, code="GA")
        b = Tax(is_default=0, name="Global B", percentage=10, code="GB")
        db_session.add_all([a, b])
        db_session.commit()
        db_session.refresh(a)
        db_session.refresh(b)

        await tax_service.set_country_default(b.id_tax)

        db_session.expire_all()
        assert db_session.get(Tax, a.id_tax).is_default == 0
        assert db_session.get(Tax, b.id_tax).is_default == 1

    async def test_update_tax_clears_id_country(self, tax_service, it_country, db_session):
        tax = Tax(
            id_country=it_country.id_country,
            is_default=0,
            name="Move to global",
            percentage=22,
            code="MV",
        )
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        updated = await tax_service.update_tax(
            tax.id_tax,
            TaxSchema(
                id_country=None,
                is_default=1,
                name="Move to global",
                percentage=22,
                code="MV",
            ),
        )
        assert updated.id_country is None
        assert updated.is_default == 1


@pytest.fixture
def it_country(db_session):
    country = Country(id_origin=1, name="Italy", iso_code="IT")
    db_session.add(country)
    db_session.commit()
    db_session.refresh(country)
    return country
