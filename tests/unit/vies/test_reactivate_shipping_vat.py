"""Unit test — riattivazione IVA spedizione su not_eligible."""
import pytest

from src.models.order import Order, ViesStatus
from src.models.order_detail import OrderDetail
from src.models.shipping import Shipping
from src.models.tax import Tax
from src.repository.order_repository import OrderRepository
from src.services.routers.order_service import OrderService
from src.vies.exemption_calculation import reactivate_shipping_vat_for_order


@pytest.fixture
def order_service(db_session):
    return OrderService(OrderRepository(db_session))


@pytest.fixture
def order_vies_eligible_with_shipping(db_session):
    tax22 = Tax(name="IVA 22%", percentage=22, code="T22", is_default=0)
    tax0 = Tax(name="IVA 0%", percentage=0, code="T0", is_default=0)
    db_session.add_all([tax22, tax0])
    db_session.commit()

    shipping = Shipping(
        id_carrier_api=1,
        id_shipping_state=1,
        id_tax=tax0.id_tax,
        price_tax_incl=10.00,
        price_tax_excl=10.00,
        weight=1.0,
    )
    db_session.add(shipping)
    db_session.commit()

    order = Order(
        id_order_state=2,
        vies_status=ViesStatus.ELIGIBLE,
        id_shipping=shipping.id_shipping,
        total_price_with_tax=110.00,
        total_price_net=110.00,
        products_total_price_with_tax=100.00,
        products_total_price_net=100.00,
        total_discounts=0,
    )
    db_session.add(order)
    db_session.commit()

    detail = OrderDetail(
        id_order=order.id_order,
        id_tax=tax0.id_tax,
        product_name="Prodotto",
        product_qty=1,
        unit_price_with_tax=100.00,
        unit_price_net=100.00,
        total_price_with_tax=100.00,
        total_price_net=100.00,
    )
    db_session.add(detail)
    db_session.commit()
    return order, detail, shipping, tax22


def test_reactivate_shipping_vat_adds_tax_on_excl(db_session, order_vies_eligible_with_shipping):
    order, _detail, shipping, tax22 = order_vies_eligible_with_shipping

    reactivate_shipping_vat_for_order(db_session, order)
    db_session.commit()
    db_session.expire_all()

    s = db_session.get(Shipping, shipping.id_shipping)
    assert s.id_tax == tax22.id_tax
    assert float(s.price_tax_excl) == 10.00
    assert float(s.price_tax_incl) == 12.20


@pytest.mark.asyncio
async def test_update_vies_status_not_eligible_does_not_touch_lines_or_totals(
    order_service, db_session, order_vies_eligible_with_shipping, event_bus_spy
):
    order, detail, shipping, tax22 = order_vies_eligible_with_shipping
    order_id = order.id_order
    detail_id = detail.id_order_detail

    updated = await order_service.update_vies_status(
        order_id, ViesStatus.NOT_ELIGIBLE, user_id=1
    )

    assert updated.vies_status == ViesStatus.NOT_ELIGIBLE

    db_session.expire_all()
    o = db_session.get(Order, order_id)
    d = db_session.get(OrderDetail, detail_id)
    s = db_session.get(Shipping, shipping.id_shipping)

    assert float(o.total_price_with_tax) == 110.00
    assert float(o.total_price_net) == 110.00
    assert float(d.total_price_with_tax) == 100.00
    assert float(d.total_price_net) == 100.00
    assert s.id_tax == tax22.id_tax
    assert float(s.price_tax_incl) == 12.20
    assert float(s.price_tax_excl) == 10.00


@pytest.mark.asyncio
async def test_update_vies_status_idempotent(
    order_service, db_session, order_vies_eligible_with_shipping, event_bus_spy
):
    order, _, _, _ = order_vies_eligible_with_shipping

    first = await order_service.update_vies_status(
        order.id_order, ViesStatus.NOT_ELIGIBLE, user_id=1
    )
    second = await order_service.update_vies_status(
        order.id_order, ViesStatus.NOT_ELIGIBLE, user_id=1
    )

    assert first.vies_status == ViesStatus.NOT_ELIGIBLE
    assert second.vies_status == ViesStatus.NOT_ELIGIBLE
