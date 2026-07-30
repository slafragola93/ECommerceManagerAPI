"""Unit test — sync is_payed=false quando add_order_detail aumenta il totale."""
from datetime import datetime

import pytest

from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.tax import Tax
from src.repository.order_repository import OrderRepository
from src.schemas.order_detail_schema import OrderDetailCreateSchema
from src.services.routers.order_service import OrderService


@pytest.fixture
def tax(db_session):
    t = Tax(name="IVA 22", percentage=22.0, is_default=1)
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


@pytest.fixture
def paid_order_with_line(db_session, tax):
    o = Order(
        id_order_state=1,
        is_invoice_requested=False,
        is_payed=True,
        total_price_with_tax=50.0,
        total_price_net=40.98,
        products_total_price_net=40.98,
        products_total_price_with_tax=50.0,
    )
    db_session.add(o)
    db_session.commit()
    db_session.refresh(o)

    detail = OrderDetail(
        id_order=o.id_order,
        id_order_document=0,
        id_origin=0,
        id_tax=tax.id_tax,
        product_name="Prodotto iniziale",
        product_reference="SKU1",
        product_qty=1,
        product_weight=1.0,
        unit_price_net=40.98,
        unit_price_with_tax=50.0,
        total_price_net=40.98,
        total_price_with_tax=50.0,
    )
    db_session.add(detail)
    db_session.commit()
    return o


@pytest.mark.asyncio
async def test_add_order_detail_clears_is_payed_when_total_increases(
    db_session, paid_order_with_line, tax
):
    service = OrderService(OrderRepository(db_session))
    assert paid_order_with_line.is_payed is True
    previous_total = float(paid_order_with_line.total_price_with_tax)

    await service.add_order_detail(
        paid_order_with_line.id_order,
        OrderDetailCreateSchema(
            id_tax=tax.id_tax,
            product_name="Nuovo prodotto",
            product_qty=1,
            product_weight=1.0,
            unit_price_with_tax=49.90,
            total_price_with_tax=49.90,
        ),
    )

    db_session.refresh(paid_order_with_line)
    assert float(paid_order_with_line.total_price_with_tax) > previous_total
    assert paid_order_with_line.is_payed is False
