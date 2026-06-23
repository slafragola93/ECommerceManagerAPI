"""Scenario numerico: apply VIES con spedizione — traccia campi DB prima/dopo."""
import pytest

from src.models.order import Order, ViesStatus
from src.models.order_detail import OrderDetail
from src.models.shipping import Shipping
from src.models.tax import Tax
from src.repository.order_repository import OrderRepository
from src.services.routers.order_service import OrderService


@pytest.fixture
def order_service(db_session):
    return OrderService(OrderRepository(db_session))


@pytest.fixture
def order_with_shipping(db_session):
    tax22 = Tax(name="IVA 22%", percentage=22, code="T22", is_default=0)
    db_session.add(tax22)
    db_session.commit()

    shipping = Shipping(
        id_carrier_api=1,
        id_shipping_state=1,
        id_tax=tax22.id_tax,
        price_tax_incl=12.20,
        price_tax_excl=10.00,
        weight=1.0,
    )
    db_session.add(shipping)
    db_session.commit()

    order = Order(
        id_order_state=2,
        is_payed=True,
        is_invoice_requested=True,
        vies_status=ViesStatus.NOT_ELIGIBLE,
        id_shipping=shipping.id_shipping,
        total_price_with_tax=134.20,
        total_price_net=110.00,
        products_total_price_with_tax=122.00,
        products_total_price_net=100.00,
        total_discounts=0,
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    detail = OrderDetail(
        id_order=order.id_order,
        id_tax=tax22.id_tax,
        product_name="Prodotto DE B2B",
        product_qty=1,
        unit_price_with_tax=122.00,
        unit_price_net=100.00,
        total_price_with_tax=122.00,
        total_price_net=100.00,
    )
    db_session.add(detail)
    db_session.commit()
    return order, detail, shipping, tax22


@pytest.mark.asyncio
async def test_vies_apply_trace_with_shipping(
    order_service, db_session, order_with_shipping, event_bus_spy, capsys
):
    order, detail, shipping, tax22 = order_with_shipping

    def fmt_state(phase: str) -> str:
        db_session.expire_all()
        o = db_session.get(Order, order.id_order)
        d = db_session.get(OrderDetail, detail.id_order_detail)
        s = db_session.get(Shipping, shipping.id_shipping)
        tax_d = db_session.get(Tax, d.id_tax)
        tax_s = db_session.get(Tax, s.id_tax)
        lines = [
            f"\n--- {phase} ---",
            f"orders.vies_status = {o.vies_status}",
            f"orders.total_price_with_tax = {float(o.total_price_with_tax)}",
            f"orders.total_price_net = {float(o.total_price_net)}",
            f"orders.products_total (net/gross) = {float(o.products_total_price_net)} / {float(o.products_total_price_with_tax)}",
            f"order_details.id_tax = {d.id_tax} ({float(tax_d.percentage)}%)",
            f"order_details (net/gross) = {float(d.total_price_net)} / {float(d.total_price_with_tax)}",
            f"shipments.id_tax = {s.id_tax} ({float(tax_s.percentage)}%)",
            f"shipments (excl/incl) = {float(s.price_tax_excl)} / {float(s.price_tax_incl)}",
            f"IVA prodotti = {float(d.total_price_with_tax) - float(d.total_price_net):.2f}",
            f"IVA spedizione = {float(s.price_tax_incl) - float(s.price_tax_excl):.2f}",
            f"IVA ordine totale = {float(o.total_price_with_tax) - float(o.total_price_net):.2f}",
        ]
        return "\n".join(lines)

    print(fmt_state("PRIMA"))
    await order_service.apply_vies_exemption(order.id_order, user_id=42)
    print(fmt_state("DOPO"))

    db_session.expire_all()
    o = db_session.get(Order, order.id_order)
    d = db_session.get(OrderDetail, detail.id_order_detail)
    s = db_session.get(Shipping, shipping.id_shipping)
    zero_tax = db_session.query(Tax).filter(Tax.percentage == 0).first()

    assert o.vies_status == ViesStatus.ELIGIBLE
    assert d.id_tax == zero_tax.id_tax
    assert float(d.total_price_with_tax) == 100.00
    assert float(d.total_price_net) == 100.00
    # Spedizione: IVA rimossa (12,20 → 10)
    assert s.id_tax == zero_tax.id_tax
    assert float(s.price_tax_incl) == 10.00
    assert float(s.price_tax_excl) == 10.00
    # Totali ordine: prodotti + spedizione netti
    assert float(o.products_total_price_net) == 100.00
    assert float(o.products_total_price_with_tax) == 100.00
    assert float(o.total_price_with_tax) == 110.00
    assert float(o.total_price_net) == 110.00
