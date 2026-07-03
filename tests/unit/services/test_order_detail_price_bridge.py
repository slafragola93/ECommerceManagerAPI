"""Unit test — order_service update_order_detail con BE-1 bridge."""
import pytest

from src.models.order import Order, ViesStatus
from src.models.order_detail import OrderDetail
from src.models.tax import Tax
from src.repository.order_repository import OrderRepository
from src.schemas.order_detail_schema import OrderDetailUpdateSchema
from src.services.routers.order_service import OrderService


@pytest.fixture
def order_service(db_session):
    return OrderService(OrderRepository(db_session))


@pytest.fixture
def vies_line(db_session):
    tax0 = Tax(name="IVA 0%", percentage=0, code="T0", is_default=0)
    tax22 = Tax(name="IVA 22%", percentage=22, code="T22", is_default=0)
    db_session.add_all([tax0, tax22])
    db_session.commit()

    order = Order(
        id_order_state=1,
        vies_status=ViesStatus.ELIGIBLE,
        total_price_with_tax=100.0,
        total_price_net=100.0,
        products_total_price_with_tax=100.0,
        products_total_price_net=100.0,
    )
    db_session.add(order)
    db_session.commit()

    detail = OrderDetail(
        id_order=order.id_order,
        id_tax=tax0.id_tax,
        product_name="Item",
        product_qty=2,
        unit_price_with_tax=50.0,
        unit_price_net=50.0,
        total_price_with_tax=100.0,
        total_price_net=100.0,
    )
    db_session.add(detail)
    db_session.commit()
    return order, detail, tax22


@pytest.mark.asyncio
async def test_update_with_complete_payload_persists_fe_prices(
    order_service, db_session, vies_line
):
    order, detail, tax22 = vies_line

    updated = await order_service.update_order_detail(
        order.id_order,
        detail.id_order_detail,
        OrderDetailUpdateSchema(
            id_tax=tax22.id_tax,
            unit_price_net=50.0,
            unit_price_with_tax=61.0,
            total_price_net=100.0,
            total_price_with_tax=122.0,
        ),
    )

    assert float(updated.unit_price_net) == 50.0
    assert float(updated.unit_price_with_tax) == 61.0
    assert float(updated.total_price_net) == 100.0
    assert float(updated.total_price_with_tax) == 122.0
    assert updated.id_tax == tax22.id_tax


@pytest.mark.asyncio
async def test_update_id_tax_only_uses_legacy(order_service, db_session, vies_line):
    order, detail, tax22 = vies_line

    updated = await order_service.update_order_detail(
        order.id_order,
        detail.id_order_detail,
        OrderDetailUpdateSchema(id_tax=tax22.id_tax),
    )

    assert updated.id_tax == tax22.id_tax
    assert float(updated.total_price_with_tax) == pytest.approx(122.0, abs=0.02)
