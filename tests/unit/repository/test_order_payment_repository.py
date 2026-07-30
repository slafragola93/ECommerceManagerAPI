"""Unit test — OrderPayment repository (CRUD, sum, get_by_order)."""
from datetime import datetime

import pytest

from src.models.order import Order
from src.models.order_payment import OrderPayment
from src.models.payment import Payment
from src.repository.order_payment_repository import OrderPaymentRepository


@pytest.fixture
def payment_method(db_session):
    pm = Payment(name="Bonifico", is_complete_payment=False, fiscal_mode_payment="MP05")
    db_session.add(pm)
    db_session.commit()
    db_session.refresh(pm)
    return pm


@pytest.fixture
def order(db_session):
    o = Order(
        id_order_state=1,
        is_invoice_requested=False,
        is_payed=True,
        total_price_with_tax=100.0,
        products_total_price_net=80.0,
        products_total_price_with_tax=100.0,
    )
    db_session.add(o)
    db_session.commit()
    db_session.refresh(o)
    return o


def test_create_and_get_by_order(db_session, order, payment_method):
    repo = OrderPaymentRepository(db_session)
    entity = OrderPayment(
        id_order=order.id_order,
        id_payment=payment_method.id_payment,
        amount=40.0,
        is_paid=True,
        date_add=datetime.now(),
    )
    created = repo.create(entity)
    assert created.id_order_payment is not None

    rows = repo.get_by_order_id(order.id_order)
    assert len(rows) == 1
    assert float(rows[0].amount) == 40.0


def test_sum_amounts_by_order(db_session, order, payment_method):
    repo = OrderPaymentRepository(db_session)
    repo.create(
        OrderPayment(
            id_order=order.id_order,
            id_payment=payment_method.id_payment,
            amount=60.0,
            is_paid=True,
            date_add=datetime.now(),
        )
    )
    repo.create(
        OrderPayment(
            id_order=order.id_order,
            id_payment=payment_method.id_payment,
            amount=40.0,
            is_paid=False,
            date_add=datetime.now(),
        )
    )

    assert repo.sum_amounts_by_order(order.id_order) == 100.0
    assert repo.sum_amounts_by_order(order.id_order, only_paid=True) == 60.0


def test_get_by_id_and_order(db_session, order, payment_method):
    repo = OrderPaymentRepository(db_session)
    created = repo.create(
        OrderPayment(
            id_order=order.id_order,
            id_payment=payment_method.id_payment,
            amount=10.0,
            is_paid=False,
            date_add=datetime.now(),
        )
    )
    found = repo.get_by_id_and_order(created.id_order_payment, order.id_order)
    assert found is not None
    assert found.id_order_payment == created.id_order_payment
    assert repo.get_by_id_and_order(created.id_order_payment, 99999) is None


def test_formatted_output_includes_order_payments(db_session, order, payment_method):
    from src.repository.order_repository import OrderRepository

    db_session.add(
        OrderPayment(
            id_order=order.id_order,
            id_payment=payment_method.id_payment,
            amount=100.0,
            is_paid=True,
            date_add=datetime.now(),
        )
    )
    db_session.commit()

    payload = OrderRepository(db_session).formatted_output(order, show_details=True)
    assert len(payload["order_payments"]) == 1
    assert payload["payment_summary"]["total_paid"] == 100.0
    assert payload["payment_summary"]["remaining_amount"] == 0.0
