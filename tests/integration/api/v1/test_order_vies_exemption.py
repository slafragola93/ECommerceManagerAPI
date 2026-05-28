"""Integration test — apply-vies-exemption + filtro vies_status."""
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.models.order import Order, ViesStatus
from src.models.order_detail import OrderDetail
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


@pytest.mark.integration
class TestOrderViesEndpoints:
    def test_apply_vies_exemption_200(self, admin_client, seeded_order):
        response = admin_client.patch(
            f"/api/v1/orders/{seeded_order.id_order}/apply-vies-exemption"
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["status"] == "success"
        assert body["data"]["vies_status"] == "eligible"

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
