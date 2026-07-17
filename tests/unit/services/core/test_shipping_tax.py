"""Unit test — aliquota spedizione per paese di consegna."""
from datetime import date

import pytest

from src.models.address import Address
from src.models.country import Country
from src.models.customer import Customer
from src.models.order import Order, ViesStatus
from src.models.order_state import OrderState
from src.models.shipping import Shipping
from src.models.tax import Tax
from src.repository.order_repository import OrderRepository
from src.repository.tax_repository import TaxRepository
from src.schemas.order_schema import OrderSchema
from src.schemas.shipping_schema import ShippingSchema
from src.services.core.shipping_tax import (
    apply_delivery_tax_to_shipping_data,
    resolve_shipping_tax_info,
)


@pytest.fixture
def it_country_tax(db_session):
    country = Country(id_origin=1, name="Italy", iso_code="IT")
    db_session.add(country)
    db_session.commit()
    tax = Tax(
        id_country=country.id_country,
        is_default=1,
        name="IVA IT 22%",
        percentage=22,
        code="VATIT",
        electronic_code="",
    )
    db_session.add(tax)
    db_session.commit()
    return country, tax


@pytest.fixture
def de_country_tax(db_session):
    country = Country(id_origin=2, name="Germany", iso_code="DE")
    db_session.add(country)
    db_session.commit()
    tax = Tax(
        id_country=country.id_country,
        is_default=1,
        name="IVA DE 19%",
        percentage=19,
        code="VATDE",
        electronic_code="",
    )
    db_session.add(tax)
    db_session.commit()
    return country, tax


@pytest.fixture
def order_state(db_session):
    state = OrderState(id_order_state=1, name="In attesa")
    db_session.add(state)
    db_session.commit()
    return state


class TestResolveShippingTaxInfo:
    def test_returns_country_default(self, db_session, it_country_tax):
        country, tax = it_country_tax
        info = resolve_shipping_tax_info(
            db_session, id_country_delivery=country.id_country
        )
        assert info["id_tax"] == tax.id_tax
        assert info["percentage"] == 22.0

    def test_vies_eligible_returns_zero_tax(self, db_session, it_country_tax, reverse_charge):
        country, _ = it_country_tax
        info = resolve_shipping_tax_info(
            db_session,
            id_country_delivery=country.id_country,
            vies_status=ViesStatus.ELIGIBLE,
        )
        assert info["id_tax"] == reverse_charge.id_tax
        assert info["percentage"] == 0.0


@pytest.fixture
def reverse_charge(db_session):
    tax = Tax(name="IVA 0% RC", percentage=0, code="RC", is_default=0)
    db_session.add(tax)
    db_session.commit()
    from src.models.app_configuration import AppConfiguration

    db_session.add(
        AppConfiguration(
            id_lang=0,
            category="vies",
            name="reverse_charge_id_tax",
            value=str(tax.id_tax),
            description="test",
            is_encrypted=False,
        )
    )
    db_session.commit()
    return tax


class TestApplyDeliveryTaxToShippingData:
    def test_sets_id_tax_and_recalculates_excl_from_incl(
        self, db_session, de_country_tax
    ):
        country, tax = de_country_tax
        data = {"price_tax_incl": 11.90, "price_tax_excl": 0.0, "id_tax": 1}
        apply_delivery_tax_to_shipping_data(
            db_session,
            data,
            id_country_delivery=country.id_country,
        )
        assert data["id_tax"] == tax.id_tax
        assert data["price_tax_excl"] == 10.00
        assert data["price_tax_incl"] == 11.90

    def test_vies_strips_vat_from_gross(self, db_session, it_country_tax, reverse_charge):
        country, tax22 = it_country_tax
        data = {
            "price_tax_incl": 12.20,
            "price_tax_excl": 10.00,
            "id_tax": tax22.id_tax,
        }
        apply_delivery_tax_to_shipping_data(
            db_session,
            data,
            id_country_delivery=country.id_country,
            vies_status=ViesStatus.ELIGIBLE,
        )
        assert data["id_tax"] == reverse_charge.id_tax
        assert data["price_tax_incl"] == 10.00
        assert data["price_tax_excl"] == 10.00


class TestOrderCreateShippingCountryTax:
    def test_create_order_shipping_gets_country_id_tax(
        self, db_session, de_country_tax, order_state
    ):
        country, de_tax = de_country_tax
        customer = Customer(
            id_origin=1,
            id_lang=1,
            firstname="Test",
            lastname="User",
            email="ship-tax@test.com",
        )
        db_session.add(customer)
        db_session.commit()

        address = Address(
            id_origin=1,
            id_country=country.id_country,
            id_customer=customer.id_customer,
            firstname="Test",
            lastname="User",
            address1="Str 1",
            city="Berlin",
            postcode="10115",
            date_add=date.today(),
        )
        db_session.add(address)
        db_session.commit()

        repo = OrderRepository(db_session)
        schema = OrderSchema(
            address_delivery=address.id_address,
            address_invoice=address.id_address,
            customer=customer.id_customer,
            id_order_state=1,
            is_invoice_requested=False,
            total_price_with_tax=122.0,
            shipping=ShippingSchema(
                id_carrier_api=1,
                price_tax_incl=11.90,
                price_tax_excl=0.0,
            ),
        )
        order_id = repo.create(schema)
        order = db_session.get(Order, order_id)
        shipping = db_session.get(Shipping, order.id_shipping)

        assert shipping.id_tax == de_tax.id_tax
        assert float(shipping.price_tax_excl) == 10.00
        assert float(shipping.price_tax_incl) == 11.90


class TestDefineTaxByCountry:
    def test_define_tax_uses_country_default(self, db_session, it_country_tax):
        country, tax = it_country_tax
        repo = TaxRepository(db_session)
        assert repo.define_tax(country.id_country) == tax.id_tax
