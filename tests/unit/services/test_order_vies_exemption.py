"""Unit test — apply_vies_exemption (BE-VIES-2)."""
import pytest

from src.models.order import Order, ViesStatus
from src.models.order_detail import OrderDetail
from src.models.tax import Tax
from src.repository.order_repository import OrderRepository
from src.services.routers.order_service import OrderService


@pytest.fixture
def order_service(db_session):
    return OrderService(OrderRepository(db_session))


@pytest.fixture
def order_with_line(db_session):
    tax22 = Tax(name="IVA 22%", percentage=22, code="T22", is_default=0)
    db_session.add(tax22)
    db_session.commit()
    order = Order(
        id_order_state=1,
        is_invoice_requested=True,
        vies_status=ViesStatus.NOT_ELIGIBLE,
        total_price_with_tax=122.0,
        total_price_net=100.0,
        products_total_price_with_tax=122.0,
        products_total_price_net=100.0,
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    detail = OrderDetail(
        id_order=order.id_order,
        id_tax=tax22.id_tax,
        product_name="Prodotto test",
        product_qty=1,
        unit_price_with_tax=122.0,
        unit_price_net=100.0,
        total_price_with_tax=122.0,
        total_price_net=100.0,
    )
    db_session.add(detail)
    db_session.commit()
    return order, detail, tax22


@pytest.mark.asyncio
class TestApplyViesExemption:
    async def test_sets_zero_tax_and_eligible_status(
        self, order_service, db_session, order_with_line, event_bus_spy
    ):
        order, detail, _ = order_with_line
        updated = await order_service.apply_vies_exemption(order.id_order, user_id=42)

        assert updated.vies_status == ViesStatus.ELIGIBLE
        db_session.expire_all()
        refreshed_detail = db_session.get(OrderDetail, detail.id_order_detail)
        zero_tax = db_session.query(Tax).filter(Tax.percentage == 0).first()
        assert zero_tax is not None
        assert refreshed_detail.id_tax == zero_tax.id_tax
        assert float(refreshed_detail.total_price_with_tax) == 122.0
        assert float(refreshed_detail.total_price_net) == 122.0

    async def test_bulk_atomic_rollback_on_missing_order(
        self, order_service, db_session, order_with_line, event_bus_spy
    ):
        order, detail, tax22 = order_with_line
        original_tax_id = detail.id_tax
        with pytest.raises(Exception):
            await order_service.bulk_apply_vies_exemption(
                [order.id_order, 999999], user_id=1
            )
        db_session.expire_all()
        refreshed_order = db_session.get(Order, order.id_order)
        refreshed_detail = db_session.get(OrderDetail, detail.id_order_detail)
        assert refreshed_order.vies_status == ViesStatus.NOT_ELIGIBLE
        assert refreshed_detail.id_tax == original_tax_id == tax22.id_tax
