"""Unit test — payment_due_date su ordini (schema, repository, update)."""
from datetime import date, datetime

from src.models.order import Order
from src.repository.order_repository import OrderRepository
from src.schemas.order_schema import OrderIdSchema, OrderUpdateSchema


def test_order_id_schema_declares_payment_due_date_field():
    assert "payment_due_date" in OrderIdSchema.model_fields


def test_formatted_output_payment_due_date_roundtrip(db_session):
    order = Order(
        id_order_state=1,
        is_invoice_requested=True,
        total_price_with_tax=100.0,
        products_total_price_net=80.0,
        products_total_price_with_tax=100.0,
        payment_due_date=date(2026, 8, 14),
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    payload = OrderRepository(db_session).formatted_output(order, show_details=False)
    assert payload["payment_due_date"] == date(2026, 8, 14)

    validated = OrderIdSchema.model_validate(payload)
    assert validated.payment_due_date == date(2026, 8, 14)


def test_update_order_payment_due_date(db_session):
    order = Order(
        id_order_state=1,
        is_invoice_requested=True,
        total_price_with_tax=50.0,
        products_total_price_net=40.0,
        products_total_price_with_tax=50.0,
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    repo = OrderRepository(db_session)
    updated = repo.update(
        order,
        OrderUpdateSchema(payment_due_date=date(2026, 9, 1)),
    )
    assert updated.payment_due_date == date(2026, 9, 1)

    payload = repo.formatted_output(updated, show_details=False)
    assert payload["payment_due_date"] == date(2026, 9, 1)


def test_update_order_clear_payment_due_date(db_session):
    order = Order(
        id_order_state=1,
        is_invoice_requested=True,
        total_price_with_tax=50.0,
        products_total_price_net=40.0,
        products_total_price_with_tax=50.0,
        payment_due_date=date(2026, 9, 1),
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    repo = OrderRepository(db_session)
    updated = repo.update(order, OrderUpdateSchema(payment_due_date=None))
    assert updated.payment_due_date is None
