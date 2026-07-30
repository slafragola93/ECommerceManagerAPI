"""Unit test — OrderPaymentService (CRUD, summary, sync is_payed)."""
from datetime import datetime

import pytest

from src.models.order import Order
from src.models.payment import Payment
from src.repository.order_payment_repository import OrderPaymentRepository
from src.repository.order_repository import OrderRepository
from src.repository.payment_repository import PaymentRepository
from src.schemas.order_payment_schema import (
    OrderPaymentCreateSchema,
    OrderPaymentPaidStatusSchema,
    OrderPaymentUpdateSchema,
)
from src.services.routers.order_payment_service import OrderPaymentService


@pytest.fixture
def payment_method(db_session):
    pm = Payment(name="Carta", is_complete_payment=True, fiscal_mode_payment="MP08")
    db_session.add(pm)
    db_session.commit()
    db_session.refresh(pm)
    return pm


@pytest.fixture
def paid_order(db_session, payment_method):
    o = Order(
        id_order_state=1,
        id_payment=payment_method.id_payment,
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


@pytest.fixture
def service(db_session):
    return OrderPaymentService(
        order_payment_repository=OrderPaymentRepository(db_session),
        order_repository=OrderRepository(db_session),
        payment_repository=PaymentRepository(db_session),
    )


@pytest.mark.asyncio
async def test_create_unpaid_payment_clears_is_payed(service, paid_order, payment_method, db_session):
    assert paid_order.is_payed is True
    await service.create_order_payment(
        paid_order.id_order,
        OrderPaymentCreateSchema(
            id_payment=payment_method.id_payment,
            amount=49.90,
            is_paid=False,
            note="Saldo nuovo articolo",
        ),
    )
    db_session.refresh(paid_order)
    assert paid_order.is_payed is False


@pytest.mark.asyncio
async def test_list_order_payments_summary(service, paid_order, payment_method):
    await service.create_order_payment(
        paid_order.id_order,
        OrderPaymentCreateSchema(
            id_payment=payment_method.id_payment,
            amount=60.0,
            is_paid=True,
        ),
    )
    await service.create_order_payment(
        paid_order.id_order,
        OrderPaymentCreateSchema(
            id_payment=payment_method.id_payment,
            amount=40.0,
            is_paid=False,
        ),
    )
    result = await service.list_order_payments(paid_order.id_order)
    assert result["total"] == 2
    assert result["payment_summary"]["total_scheduled"] == 100.0
    assert result["payment_summary"]["total_paid"] == 60.0
    assert result["payment_summary"]["remaining_amount"] == 40.0


@pytest.mark.asyncio
async def test_update_and_mark_paid(service, paid_order, payment_method, db_session):
    created = await service.create_order_payment(
        paid_order.id_order,
        OrderPaymentCreateSchema(
            id_payment=payment_method.id_payment,
            amount=25.0,
            is_paid=False,
        ),
    )
    updated = await service.update_order_payment(
        paid_order.id_order,
        created.id_order_payment,
        OrderPaymentUpdateSchema(amount=30.0, note="Aggiornato"),
    )
    assert float(updated.amount) == 30.0
    assert updated.note == "Aggiornato"

    paid = await service.update_paid_status(
        paid_order.id_order,
        created.id_order_payment,
        OrderPaymentPaidStatusSchema(is_paid=True),
    )
    assert paid.is_paid is True
    assert paid.payment_date is not None


@pytest.mark.asyncio
async def test_delete_order_payment(service, paid_order, payment_method):
    created = await service.create_order_payment(
        paid_order.id_order,
        OrderPaymentCreateSchema(
            id_payment=payment_method.id_payment,
            amount=10.0,
            is_paid=True,
        ),
    )
    ok = await service.delete_order_payment(paid_order.id_order, created.id_order_payment)
    assert ok is True
    result = await service.list_order_payments(paid_order.id_order)
    assert result["total"] == 0
