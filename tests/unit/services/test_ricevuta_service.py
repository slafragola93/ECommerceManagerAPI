"""Test service ricevute."""
from datetime import date
from decimal import Decimal

import pytest

from src.core.container_config import get_configured_container
from src.models.customer import Customer
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.ricevuta import ORDER_STATE_SPEDIZIONE_CONFERMATA, Ricevuta, RicevutaStato
from src.models.shipping import Shipping
from src.models.tax import Tax
from src.schemas.ricevuta_schema import RicevutaFiltersSchema, RicevutaStatoSchema
from src.services.interfaces.ricevuta_service_interface import IRicevutaService


@pytest.fixture
def tax(db_session):
    row = Tax(name="IVA 22%", percentage=22, code="22", is_default=0)
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


@pytest.fixture
def service(db_session):
    container = get_configured_container()
    return container.resolve_with_session(IRicevutaService, db_session)


@pytest.fixture
def fixtures(db_session, tax):
    customer = Customer(
        id_lang=1,
        firstname="Luigi",
        lastname="Verdi",
        email="luigi.v@example.com",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    order = Order(
        id_customer=customer.id_customer,
        id_order_state=1,
        reference="ORD-SVC-001",
        is_payed=True,
        payment_date=date(2026, 6, 1),
        total_price_with_tax=Decimal("244.00"),
        total_price_net=Decimal("200.00"),
        products_total_price_with_tax=Decimal("244.00"),
        products_total_price_net=Decimal("200.00"),
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    detail = OrderDetail(
        id_order=order.id_order,
        id_tax=tax.id_tax,
        product_name="Articolo test",
        product_reference="REF-1",
        product_qty=2,
        unit_price_with_tax=Decimal("122.00"),
        unit_price_net=Decimal("100.00"),
        total_price_with_tax=Decimal("244.00"),
        total_price_net=Decimal("200.00"),
    )
    db_session.add(detail)
    db_session.commit()

    ricevuta = Ricevuta(
        numero=7,
        anno=2026,
        id_order=order.id_order,
        id_customer=customer.id_customer,
        data_incasso=date(2026, 6, 1),
        data_emissione=date(2026, 6, 5),
        stato=RicevutaStato.EMESSA,
    )
    db_session.add(ricevuta)
    db_session.commit()
    db_session.refresh(ricevuta)

    return {"customer": customer, "order": order, "ricevuta": ricevuta}


def test_get_ricevuta_detail_with_live_data(service, fixtures):
    ricevuta = fixtures["ricevuta"]
    order = fixtures["order"]
    customer = fixtures["customer"]

    result = service.get_ricevuta(ricevuta.id_ricevuta)

    assert result.numero == 7
    assert result.anno == 2026
    assert result.customer.id_customer == customer.id_customer
    assert result.order.id_order == order.id_order
    assert result.is_modifiable is True
    assert len(result.order_details) == 1
    assert result.order_details[0].product_name == "Articolo test"
    assert result.order_details[0].is_shipping is False


def test_get_ricevuta_includes_shipping_line_and_totals(service, db_session, tax):
    customer = Customer(
        id_lang=1,
        firstname="Anna",
        lastname="Bianchi",
        email="anna@example.com",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    shipping = Shipping(
        id_tax=tax.id_tax,
        price_tax_excl=Decimal("10.00"),
        price_tax_incl=Decimal("12.20"),
    )
    db_session.add(shipping)
    db_session.commit()
    db_session.refresh(shipping)

    order = Order(
        id_customer=customer.id_customer,
        id_order_state=1,
        id_shipping=shipping.id_shipping,
        reference="ORD-SHIP",
        is_payed=True,
        payment_date=date(2026, 6, 2),
        total_price_with_tax=Decimal("134.20"),
        total_price_net=Decimal("110.00"),
        products_total_price_with_tax=Decimal("122.00"),
        products_total_price_net=Decimal("100.00"),
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    db_session.add(
        OrderDetail(
            id_order=order.id_order,
            id_tax=tax.id_tax,
            product_name="Prodotto",
            product_reference="P-1",
            product_qty=1,
            unit_price_with_tax=Decimal("122.00"),
            unit_price_net=Decimal("100.00"),
            total_price_with_tax=Decimal("122.00"),
            total_price_net=Decimal("100.00"),
        )
    )
    ricevuta = Ricevuta(
        numero=8,
        anno=2026,
        id_order=order.id_order,
        id_customer=customer.id_customer,
        data_incasso=date(2026, 6, 2),
        data_emissione=date(2026, 6, 3),
        stato=RicevutaStato.EMESSA,
    )
    db_session.add(ricevuta)
    db_session.commit()
    db_session.refresh(ricevuta)

    result = service.get_ricevuta(ricevuta.id_ricevuta)

    assert len(result.order_details) == 2
    assert result.order_details[-1].is_shipping is True
    assert result.order_details[-1].product_name == "Spedizione"
    assert result.order.shipping_total_price_with_tax == 12.2
    assert result.order.total_price_with_tax == 134.2
    lines_gross = sum(line.total_price_with_tax or 0 for line in result.order_details)
    assert lines_gross == pytest.approx(result.order.total_price_with_tax)


def test_get_ricevuta_not_modifiable_when_order_shipped(service, db_session, fixtures):
    order = fixtures["order"]
    order.id_order_state = ORDER_STATE_SPEDIZIONE_CONFERMATA
    db_session.commit()

    result = service.get_ricevuta(fixtures["ricevuta"].id_ricevuta)
    assert result.is_modifiable is False


def test_list_ricevute_filters(service, fixtures):
    filters = RicevutaFiltersSchema(
        id_customer=fixtures["customer"].id_customer,
        stato=RicevutaStatoSchema.EMESSA,
        page=1,
        limit=10,
    )
    result = service.list_ricevute(filters)

    assert result.total == 1
    assert result.ricevute[0].numero == 7
    assert result.ricevute[0].order_reference == "ORD-SVC-001"
