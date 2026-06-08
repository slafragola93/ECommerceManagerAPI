"""Unit test TaxService — set_country_default (BE-VIES-1) + delete (BE-ALIQ-02)."""
import pytest

from src.core.exceptions import BusinessRuleException, ErrorCode
from src.models.country import Country
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.tax import Tax
from src.repository.tax_repository import TaxRepository
from src.services.routers.tax_service import TaxService
from src.vies.vies_app_configuration import set_reverse_charge_id_tax


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
    async def test_global_default_when_no_country(self, tax_service, db_session):
        tax = Tax(is_default=0, name="Global Tax", percentage=22, code="X")
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        result = await tax_service.set_country_default(tax.id_tax)
        assert result.is_default == 1
        assert result.id_country is None

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


@pytest.mark.asyncio
class TestTaxServiceDelete:
    async def test_delete_unused_tax(self, tax_service, db_session):
        tax = Tax(name="IVA 5%", percentage=5, code="T5", is_default=0)
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)
        tax_id = tax.id_tax

        assert await tax_service.delete_tax(tax_id) is True
        assert TaxRepository(db_session).get_tax_by_id(tax_id) is None

    async def test_delete_tax_in_use_by_order_raises(self, tax_service, db_session):
        tax = Tax(name="IVA 22%", percentage=22, code="T22", is_default=0)
        db_session.add(tax)
        db_session.commit()
        order = Order(
            id_order_state=1,
            total_price_with_tax=50.0,
            total_price_net=40.0,
            products_total_price_with_tax=50.0,
            products_total_price_net=40.0,
        )
        db_session.add(order)
        db_session.commit()
        db_session.add(
            OrderDetail(
                id_order=order.id_order,
                id_tax=tax.id_tax,
                product_name="Item",
                product_qty=1,
                unit_price_with_tax=50.0,
                unit_price_net=40.0,
                total_price_with_tax=50.0,
                total_price_net=40.0,
            )
        )
        db_session.commit()

        with pytest.raises(BusinessRuleException) as exc_info:
            await tax_service.delete_tax(tax.id_tax)

        exc = exc_info.value
        assert exc.status_code == 422
        assert exc.error_code == ErrorCode.TAX_IN_USE.value
        assert exc.details["orders"] == 1
        assert exc.details["documents"] == 0
        assert exc.details["is_reverse_charge"] is False

    async def test_delete_tax_reverse_charge_raises(self, tax_service, db_session):
        tax = Tax(name="IVA 0% VIES", percentage=0, code="V0", is_default=0)
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)
        set_reverse_charge_id_tax(db_session, tax.id_tax)

        with pytest.raises(BusinessRuleException) as exc_info:
            await tax_service.delete_tax(tax.id_tax)

        exc = exc_info.value
        assert exc.status_code == 422
        assert exc.error_code == ErrorCode.TAX_IN_USE.value
        assert exc.details["is_reverse_charge"] is True
        assert exc.details["orders"] == 0

    async def test_delete_unused_tax_invalidates_init_cache(
        self, tax_service, db_session, monkeypatch
    ):
        calls = []

        async def fake_invalidate():
            calls.append(True)

        monkeypatch.setattr(
            "src.services.routers.tax_service.invalidate_init_data_cache",
            fake_invalidate,
        )

        tax = Tax(name="IVA 8%", percentage=8, code="T8", is_default=0)
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        await tax_service.delete_tax(tax.id_tax)

        assert calls == [True]

    async def test_delete_in_use_does_not_invalidate_cache(
        self, tax_service, db_session, monkeypatch
    ):
        calls = []

        async def fake_invalidate():
            calls.append(True)

        monkeypatch.setattr(
            "src.services.routers.tax_service.invalidate_init_data_cache",
            fake_invalidate,
        )

        tax = Tax(name="IVA 22%", percentage=22, code="T22", is_default=0)
        db_session.add(tax)
        db_session.commit()
        order = Order(
            id_order_state=1,
            total_price_with_tax=50.0,
            total_price_net=40.0,
            products_total_price_with_tax=50.0,
            products_total_price_net=40.0,
        )
        db_session.add(order)
        db_session.commit()
        db_session.add(
            OrderDetail(
                id_order=order.id_order,
                id_tax=tax.id_tax,
                product_name="Item",
                product_qty=1,
                unit_price_with_tax=50.0,
                unit_price_net=40.0,
                total_price_with_tax=50.0,
                total_price_net=40.0,
            )
        )
        db_session.commit()

        with pytest.raises(BusinessRuleException):
            await tax_service.delete_tax(tax.id_tax)

        assert calls == []
