"""Test creazione/eliminazione ricevute."""
from datetime import date, datetime
from decimal import Decimal

import pytest

from src.core.container_config import get_configured_container
from src.core.exceptions import BusinessRuleException, NotFoundException
from src.models.app_configuration import AppConfiguration
from src.models.customer import Customer
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.ricevuta import ORDER_STATE_SPEDIZIONE_CONFERMATA, RicevutaStato
from src.models.tax import Tax
from src.schemas.ricevuta_schema import RicevutaCreateSchema, RicevutaUpdateSchema
from src.services.interfaces.ricevuta_service_interface import IRicevutaService
from src.services.ricevute.date_utils import emission_to_rome


@pytest.fixture
def tax(db_session):
    row = Tax(name="IVA 22%", percentage=22, code="22", is_default=0)
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


@pytest.fixture
def company_info(db_session):
    rows = [
        AppConfiguration(category="company_info", name="company_name", value="Test Srl"),
        AppConfiguration(category="company_info", name="address", value="Via Roma 1"),
        AppConfiguration(category="company_info", name="city", value="Milano"),
    ]
    db_session.add_all(rows)
    db_session.commit()


@pytest.fixture
def service(db_session):
    container = get_configured_container()
    return container.resolve_with_session(IRicevutaService, db_session)


@pytest.fixture
def order_setup(db_session, tax, company_info):
    customer = Customer(
        id_lang=1,
        firstname="Anna",
        lastname="Bianchi",
        email="anna.b@example.com",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    order = Order(
        id_customer=customer.id_customer,
        id_order_state=1,
        reference="ORD-CREATE-001",
        is_payed=True,
        payment_date=date(2026, 7, 1),
        total_price_with_tax=Decimal("122.00"),
        total_price_net=Decimal("100.00"),
        products_total_price_with_tax=Decimal("122.00"),
        products_total_price_net=Decimal("100.00"),
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    detail = OrderDetail(
        id_order=order.id_order,
        id_tax=tax.id_tax,
        product_name="Prodotto A",
        product_reference="PA-1",
        product_qty=1,
        unit_price_with_tax=Decimal("122.00"),
        unit_price_net=Decimal("100.00"),
        total_price_with_tax=Decimal("122.00"),
        total_price_net=Decimal("100.00"),
    )
    db_session.add(detail)
    db_session.commit()

    return {"customer": customer, "order": order}


def test_create_ricevuta(service, order_setup):
    order = order_setup["order"]
    result = service.create_ricevuta(
        RicevutaCreateSchema(id_order=order.id_order, data_emissione=date(2026, 7, 8))
    )

    assert result.numero == 1
    assert result.anno == 2026
    assert result.id_order == order.id_order
    assert result.data_incasso == date(2026, 7, 1)
    assert emission_to_rome(result.data_emissione).date() == date(2026, 7, 8)
    assert result.stato.value == "emessa"
    assert result.pdf_path is not None
    assert result.pdf_generated_at is not None
    assert len(result.order_details) == 1


def test_create_ricevuta_with_date_only_string(service, order_setup):
    order = order_setup["order"]
    payload = RicevutaCreateSchema.model_validate(
        {"id_order": order.id_order, "data_emissione": "2026-07-08"}
    )
    result = service.create_ricevuta(payload)

    assert result.pdf_path is not None
    assert emission_to_rome(result.data_emissione).date() == date(2026, 7, 8)


def test_create_ricevuta_with_iso_datetime_string(service, order_setup):
    order = order_setup["order"]
    payload = RicevutaCreateSchema.model_validate(
        {"id_order": order.id_order, "data_emissione": "2026-07-08T14:30:00"}
    )
    result = service.create_ricevuta(payload)

    assert result.pdf_path is not None
    local = emission_to_rome(result.data_emissione)
    assert local.date() == date(2026, 7, 8)
    assert local.hour == 14
    assert local.minute == 30


def test_create_ricevuta_duplicate_blocked(service, order_setup):
    order = order_setup["order"]
    service.create_ricevuta(RicevutaCreateSchema(id_order=order.id_order))

    with pytest.raises(BusinessRuleException):
        service.create_ricevuta(RicevutaCreateSchema(id_order=order.id_order))


def test_create_ricevuta_allowed_when_shipped(service, db_session, order_setup):
    order = order_setup["order"]
    order.id_order_state = ORDER_STATE_SPEDIZIONE_CONFERMATA
    db_session.commit()

    result = service.create_ricevuta(
        RicevutaCreateSchema(id_order=order.id_order, data_emissione=date(2026, 7, 10))
    )

    assert result.stato.value == "emessa"
    assert result.is_modifiable is False
    assert result.id_order == order.id_order


def test_delete_ricevuta_allowed_when_shipped(service, db_session, order_setup):
    order = order_setup["order"]
    created = service.create_ricevuta(
        RicevutaCreateSchema(id_order=order.id_order, data_emissione=date(2026, 7, 8))
    )
    order.id_order_state = ORDER_STATE_SPEDIZIONE_CONFERMATA
    db_session.commit()

    service.delete_ricevuta(created.id_ricevuta)

    with pytest.raises(NotFoundException):
        service.get_ricevuta(created.id_ricevuta)


def test_update_ricevuta_allowed_when_shipped(service, db_session, order_setup):
    order = order_setup["order"]
    created = service.create_ricevuta(
        RicevutaCreateSchema(id_order=order.id_order, data_emissione=date(2026, 7, 8))
    )
    order.id_order_state = ORDER_STATE_SPEDIZIONE_CONFERMATA
    db_session.commit()

    updated = service.update_ricevuta(
        created.id_ricevuta,
        RicevutaUpdateSchema(data_emissione=datetime(2026, 7, 15, 16, 45)),
    )
    local = emission_to_rome(updated.data_emissione)
    assert local.date() == date(2026, 7, 15)
    assert local.hour == 16
    assert local.minute == 45
    assert updated.is_modifiable is False


def test_update_and_delete_ricevuta(service, order_setup):
    order = order_setup["order"]
    created = service.create_ricevuta(
        RicevutaCreateSchema(id_order=order.id_order, data_emissione=date(2026, 7, 8))
    )
    pdf_path = created.pdf_path

    updated = service.update_ricevuta(
        created.id_ricevuta,
        RicevutaUpdateSchema(data_emissione=datetime(2026, 7, 10, 9, 0)),
    )
    assert emission_to_rome(updated.data_emissione).date() == date(2026, 7, 10)

    service.delete_ricevuta(created.id_ricevuta, user_id=99)

    with pytest.raises(NotFoundException):
        service.get_ricevuta(created.id_ricevuta)

    from src.models.ricevuta import Ricevuta, RicevutaStato

    session = service._ricevuta_repository._session
    assert (
        session.query(Ricevuta).filter(Ricevuta.id_ricevuta == created.id_ricevuta).first()
        is None
    )
    assert (
        session.query(Ricevuta)
        .filter(
            Ricevuta.id_ricevuta == created.id_ricevuta,
            Ricevuta.stato == RicevutaStato.ANNULLATA,
        )
        .count()
        == 0
    )

    if pdf_path:
        import os

        assert not os.path.isfile(pdf_path.replace("/", os.sep))

    recreated = service.create_ricevuta(
        RicevutaCreateSchema(id_order=order.id_order, data_emissione=date(2026, 7, 11))
    )
    assert recreated.stato.value == "emessa"
    assert recreated.id_order == order.id_order
