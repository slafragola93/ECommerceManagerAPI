"""Integration test — PATCH vies-status bidirezionale."""
import pytest
from fastapi.testclient import TestClient

from src.models.order import Order, ViesStatus
from src.models.order_detail import OrderDetail
from src.models.shipping import Shipping
from src.models.tax import Tax
from src.services.routers.auth_service import get_current_user


def _admin_user():
    return {
        "username": "admin",
        "id": 1,
        "role_type": "full_crud",
        "roles": [{"name": "ADMIN", "permissions": ["C", "R", "U", "D"]}],
    }


@pytest.fixture
def admin_client(test_app):
    test_app.dependency_overrides[get_current_user] = _admin_user
    return TestClient(test_app)


@pytest.fixture
def order_with_shipping(db_session):
    tax22 = Tax(name="IVA 22%", percentage=22, code="T22P", is_default=0)
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
        id_order_state=1,
        vies_status=ViesStatus.NOT_ELIGIBLE,
        id_shipping=shipping.id_shipping,
        total_price_with_tax=122.00,
        total_price_net=100.00,
        products_total_price_with_tax=110.00,
        products_total_price_net=90.00,
    )
    db_session.add(order)
    db_session.commit()

    detail = OrderDetail(
        id_order=order.id_order,
        id_tax=tax22.id_tax,
        product_name="Item",
        product_qty=1,
        unit_price_with_tax=110.00,
        unit_price_net=90.00,
        total_price_with_tax=110.00,
        total_price_net=90.00,
    )
    db_session.add(detail)
    db_session.commit()
    return order


class TestPatchViesStatus:
    def test_eligible_applies_exemption(self, admin_client, order_with_shipping, db_session):
        oid = order_with_shipping.id_order
        response = admin_client.patch(
            f"/api/v1/orders/{oid}/vies-status",
            json={"status": "eligible"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["vies_status"] == "eligible"

        db_session.expire_all()
        shipping = db_session.get(Shipping, order_with_shipping.id_shipping)
        assert float(shipping.price_tax_incl) == float(shipping.price_tax_excl)

    def test_not_eligible_reactivates_shipping_tax_only(
        self, admin_client, order_with_shipping, db_session
    ):
        oid = order_with_shipping.id_order
        admin_client.patch(f"/api/v1/orders/{oid}/vies-status", json={"status": "eligible"})

        db_session.expire_all()
        before = db_session.get(Order, oid)
        detail_before = (
            db_session.query(OrderDetail)
            .filter(OrderDetail.id_order == oid)
            .first()
        )
        products_gross_before = float(before.products_total_price_with_tax)
        detail_gross_before = float(detail_before.total_price_with_tax)

        response = admin_client.patch(
            f"/api/v1/orders/{oid}/vies-status",
            json={"status": "not_eligible"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["vies_status"] == "not_eligible"

        db_session.expire_all()
        order = db_session.get(Order, oid)
        shipping = db_session.get(Shipping, order_with_shipping.id_shipping)
        detail = (
            db_session.query(OrderDetail)
            .filter(OrderDetail.id_order == oid)
            .first()
        )

        assert float(order.products_total_price_with_tax) == products_gross_before
        assert float(detail.total_price_with_tax) == detail_gross_before
        assert float(shipping.price_tax_excl) == 10.00
        assert float(shipping.price_tax_incl) == 12.20
