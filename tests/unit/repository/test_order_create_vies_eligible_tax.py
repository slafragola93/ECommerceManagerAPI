"""Unit test — POST create: vies_status=eligible imposta id_tax VIES sulle righe senza tax."""
import pytest

from src.models.app_configuration import AppConfiguration
from src.models.order import Order, ViesStatus
from src.models.order_detail import OrderDetail
from src.models.order_state import OrderState
from src.models.tax import Tax
from src.repository.order_repository import OrderRepository
from src.schemas.order_schema import OrderDetailSchema, OrderSchema


@pytest.fixture
def order_state(db_session):
    state = OrderState(id_order_state=1, name="In attesa")
    db_session.add(state)
    db_session.commit()
    return state


@pytest.fixture
def reverse_charge_tax(db_session):
    tax = Tax(name="IVA 0% RC", percentage=0, code="RC", is_default=0)
    db_session.add(tax)
    db_session.commit()
    db_session.add(
        AppConfiguration(
            id_lang=0,
            category="vies",
            name="reverse_charge_id_tax",
            value=str(tax.id_tax),
            description="test",
            is_encrypted=False,
        )
    )
    db_session.commit()
    return tax


@pytest.mark.asyncio
class TestOrderCreateViesEligibleTax:
    def test_lines_without_id_tax_get_reverse_charge(
        self, db_session, order_state, reverse_charge_tax
    ):
        repo = OrderRepository(db_session)
        schema = OrderSchema(
            address_delivery=0,
            address_invoice=0,
            customer=0,
            id_order_state=1,
            is_invoice_requested=True,
            vies_status=ViesStatus.ELIGIBLE,
            total_price_with_tax=100.0,
            order_details=[
                OrderDetailSchema(
                    id_product=0,
                    product_name="Item",
                    product_reference="REF1",
                    product_qty=1,
                    unit_price_with_tax=100.0,
                    unit_price_net=100.0,
                    total_price_with_tax=100.0,
                    total_price_net=100.0,
                )
            ],
        )
        order_id = repo.create(schema)
        detail = (
            db_session.query(OrderDetail)
            .filter(OrderDetail.id_order == order_id)
            .first()
        )
        assert detail is not None
        assert detail.id_tax == reverse_charge_tax.id_tax
        order = db_session.get(Order, order_id)
        assert order.vies_status == ViesStatus.ELIGIBLE

    def test_explicit_id_tax_not_overwritten(
        self, db_session, order_state, reverse_charge_tax
    ):
        other = Tax(name="IVA 22%", percentage=22, code="T22", is_default=0)
        db_session.add(other)
        db_session.commit()
        repo = OrderRepository(db_session)
        schema = OrderSchema(
            address_delivery=0,
            address_invoice=0,
            customer=0,
            id_order_state=1,
            is_invoice_requested=True,
            vies_status=ViesStatus.ELIGIBLE,
            total_price_with_tax=122.0,
            order_details=[
                OrderDetailSchema(
                    id_product=0,
                    id_tax=other.id_tax,
                    product_name="Item",
                    product_reference="REF2",
                    product_qty=1,
                    unit_price_with_tax=122.0,
                    unit_price_net=100.0,
                    total_price_with_tax=122.0,
                    total_price_net=100.0,
                )
            ],
        )
        order_id = repo.create(schema)
        detail = (
            db_session.query(OrderDetail)
            .filter(OrderDetail.id_order == order_id)
            .first()
        )
        assert detail.id_tax == other.id_tax
