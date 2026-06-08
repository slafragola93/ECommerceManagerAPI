"""Integration test — DELETE /api/v1/taxes/{id} (BE-ALIQ-02)."""
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.models.order import Order
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
def tax_with_order(db_session):
    tax = Tax(name="IVA 22%", percentage=22, code="T22", is_default=0)
    db_session.add(tax)
    db_session.commit()
    order = Order(
        id_order_state=1,
        total_price_with_tax=50.0,
        total_price_net=40.0,
        products_total_price_with_tax=50.0,
        products_total_price_net=40.0,
    )
    db_session.add(order)
    db_session.commit()
    db_session.add(
        OrderDetail(
            id_order=order.id_order,
            id_tax=tax.id_tax,
            product_name="Item",
            product_qty=1,
            unit_price_with_tax=50.0,
            unit_price_net=40.0,
            total_price_with_tax=50.0,
            total_price_net=40.0,
        )
    )
    db_session.commit()
    db_session.refresh(tax)
    return tax


@pytest.mark.integration
class TestTaxDeleteEndpoint:
    def test_delete_unused_tax_200(self, admin_client, db_session):
        tax = Tax(name="IVA 8%", percentage=8, code="T8", is_default=0)
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        response = admin_client.delete(f"/api/v1/taxes/{tax.id_tax}")
        assert response.status_code == status.HTTP_200_OK

    def test_delete_tax_in_use_422(self, admin_client, tax_with_order):
        response = admin_client.delete(f"/api/v1/taxes/{tax_with_order.id_tax}")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        body = response.json()
        assert body["error_code"] == "TAX_IN_USE"
        assert body["details"]["orders"] == 1
        assert body["details"]["is_reverse_charge"] is False
