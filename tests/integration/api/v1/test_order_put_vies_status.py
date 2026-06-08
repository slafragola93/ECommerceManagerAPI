"""Integration test — PUT vies_status + GET round-trip."""
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.models.order import Order, ViesStatus
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
    order = Order(
        id_order_state=1,
        is_invoice_requested=False,
        total_price_with_tax=100.0,
        vies_status=None,
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.mark.integration
class TestOrderPutViesStatus:
    def test_put_vies_status_then_get_returns_eligible(self, admin_client, seeded_order):
        order_id = seeded_order.id_order
        put = admin_client.put(
            f"/api/v1/orders/{order_id}",
            json={"vies_status": "eligible"},
        )
        assert put.status_code == status.HTTP_200_OK

        get = admin_client.get(f"/api/v1/orders/{order_id}")
        assert get.status_code == status.HTTP_200_OK
        assert get.json()["vies_status"] == "eligible"

    def test_put_vies_status_not_eligible(self, admin_client, seeded_order):
        order_id = seeded_order.id_order
        admin_client.put(
            f"/api/v1/orders/{order_id}",
            json={"vies_status": "not_eligible"},
        )
        get = admin_client.get(f"/api/v1/orders/{order_id}")
        assert get.json()["vies_status"] == "not_eligible"
