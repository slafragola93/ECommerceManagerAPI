"""Test repository ricevute."""
from datetime import date
from decimal import Decimal

import pytest

from src.models.customer import Customer
from src.models.order import Order
from src.models.ricevuta import Ricevuta, RicevutaStato
from src.repository.ricevuta_repository import RicevutaRepository


@pytest.fixture
def repo(db_session):
    return RicevutaRepository(db_session)


@pytest.fixture
def customer(db_session):
    row = Customer(
        id_lang=1,
        firstname="Mario",
        lastname="Rossi",
        email="mario.r@example.com",
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


@pytest.fixture
def order(db_session, customer):
    row = Order(
        id_customer=customer.id_customer,
        id_order_state=1,
        reference="ORD-RIC-001",
        is_payed=True,
        payment_date=date(2026, 3, 10),
        total_price_with_tax=Decimal("122.00"),
        total_price_net=Decimal("100.00"),
        products_total_price_with_tax=Decimal("122.00"),
        products_total_price_net=Decimal("100.00"),
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _add_ricevuta(db_session, order, customer, *, numero, anno, emissione):
    row = Ricevuta(
        numero=numero,
        anno=anno,
        id_order=order.id_order,
        id_customer=customer.id_customer,
        data_incasso=date(2026, 3, 10),
        data_emissione=emissione,
        stato=RicevutaStato.EMESSA,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_get_next_numero_starts_at_one(repo, db_session):
    assert repo.get_next_numero(2026) == 1


def test_get_next_numero_increments_within_year(repo, db_session, order, customer):
    _add_ricevuta(
        db_session, order, customer, numero=5, anno=2026, emissione=date(2026, 3, 15)
    )
    assert repo.get_next_numero(2026) == 6


def test_get_next_numero_resets_each_year(repo, db_session, order, customer):
    _add_ricevuta(
        db_session, order, customer, numero=99, anno=2025, emissione=date(2025, 12, 31)
    )
    assert repo.get_next_numero(2026) == 1


def test_list_filtered_by_order_and_stato(repo, db_session, order, customer):
    active = _add_ricevuta(
        db_session, order, customer, numero=1, anno=2026, emissione=date(2026, 4, 1)
    )
    cancelled = _add_ricevuta(
        db_session, order, customer, numero=2, anno=2026, emissione=date(2026, 4, 2)
    )
    cancelled.stato = RicevutaStato.ANNULLATA
    db_session.commit()

    rows, total = repo.list_filtered(id_order=order.id_order, stato="emessa")
    assert total == 1
    assert rows[0].id_ricevuta == active.id_ricevuta


def test_list_filtered_date_range(repo, db_session, order, customer):
    _add_ricevuta(
        db_session, order, customer, numero=1, anno=2026, emissione=date(2026, 5, 1)
    )
    _add_ricevuta(
        db_session, order, customer, numero=2, anno=2026, emissione=date(2026, 5, 20)
    )

    rows, total = repo.list_filtered(
        data_emissione_from=date(2026, 5, 10),
        data_emissione_to=date(2026, 5, 31),
    )
    assert total == 1
    assert rows[0].numero == 2
