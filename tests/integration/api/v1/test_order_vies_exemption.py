"""Integration test — apply-vies-exemption + filtro vies_status."""
import pytest
from fastapi import status
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
def seeded_order(db_session):
    tax = Tax(name="IVA 22%", percentage=22, code="T22", is_default=0)
    db_session.add(tax)
    db_session.commit()
    order = Order(
        id_order_state=1,
        vies_status=ViesStatus.NOT_ELIGIBLE,
        total_price_with_tax=50.0,
        total_price_net=40.0,
        products_total_price_with_tax=50.0,
        products_total_price_net=40.0,
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    detail = OrderDetail(
        id_order=order.id_order,
        id_tax=tax.id_tax,
        product_name="Item",
        product_qty=1,
        unit_price_with_tax=50.0,
        unit_price_net=40.0,
        total_price_with_tax=50.0,
        total_price_net=40.0,
    )
    db_session.add(detail)
    db_session.commit()
    return order


@pytest.fixture
def seeded_order_with_shipping(db_session):
    tax22 = Tax(name="IVA 22%", percentage=22, code="T22INT", is_default=0)
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
        is_invoice_requested=True,
        vies_status=ViesStatus.NOT_ELIGIBLE,
        id_shipping=shipping.id_shipping,
        total_price_with_tax=134.20,
        total_price_net=110.00,
        products_total_price_with_tax=122.00,
        products_total_price_net=100.00,
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
    return order


@pytest.mark.integration
class TestOrderViesEndpoints:
    def test_apply_vies_exemption_200(self, admin_client, seeded_order):
        response = admin_client.patch(
            f"/api/v1/orders/{seeded_order.id_order}/apply-vies-exemption"
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["status"] == "success"
        data = body["data"]
        assert data["vies_status"] == "eligible"
        # 50 € lordo @ 22% → 40,98 € netto (IVA sottratta realmente)
        assert float(data["products_total_price_with_tax"]) == pytest.approx(40.98, abs=0.01)
        assert float(data["products_total_price_net"]) == pytest.approx(40.98, abs=0.01)
        assert float(data["total_price_with_tax"]) == pytest.approx(40.98, abs=0.01)
        assert float(data["total_price_net"]) == pytest.approx(40.98, abs=0.01)

    def test_apply_vies_exemption_response_totals_with_shipping(
        self, admin_client, seeded_order_with_shipping
    ):
        order_id = seeded_order_with_shipping.id_order
        response = admin_client.patch(
            f"/api/v1/orders/{order_id}/apply-vies-exemption"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]

        assert data["vies_status"] == "eligible"
        assert float(data["products_total_price_with_tax"]) == 100.00
        assert float(data["products_total_price_net"]) == 100.00
        assert float(data["total_price_with_tax"]) == 110.00
        assert float(data["total_price_net"]) == 110.00

        get_response = admin_client.get(f"/api/v1/orders/{order_id}")
        assert get_response.status_code == status.HTTP_200_OK
        persisted = get_response.json()
        assert float(persisted["total_price_with_tax"]) == 110.00
        assert float(persisted["products_total_price_with_tax"]) == 100.00
        assert float(persisted["shipping"]["price_tax_incl"]) == 10.00
        assert float(persisted["shipping"]["price_tax_excl"]) == 10.00
        assert float(persisted["shipping"]["tax"]["percentage"]) == 0

    def test_apply_vies_exemption_404(self, admin_client):
        response = admin_client.patch("/api/v1/orders/999999/apply-vies-exemption")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_bulk_apply_vies_exemption_200(self, admin_client, seeded_order):
        response = admin_client.post(
            "/api/v1/orders/bulk-apply-vies-exemption",
            json={"order_ids": [seeded_order.id_order]},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["status"] == "success"
        assert body["data"]["processed"] == 1

    def test_list_filter_vies_status(self, admin_client, db_session):
        o1 = Order(id_order_state=1, vies_status=ViesStatus.ELIGIBLE)
        o2 = Order(id_order_state=1, vies_status=None)
        db_session.add_all([o1, o2])
        db_session.commit()

        response = admin_client.get("/api/v1/orders/?vies_status=eligible&limit=100")
        assert response.status_code == status.HTTP_200_OK
        ids = {o["id_order"] for o in response.json()["orders"]}
        assert o1.id_order in ids
