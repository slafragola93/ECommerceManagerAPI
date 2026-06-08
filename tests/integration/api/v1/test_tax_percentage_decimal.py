"""Integration test — percentage decimal in Tax API (BE-ALIQ-05)."""
import pytest
from fastapi import status
from fastapi.testclient import TestClient

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


@pytest.mark.integration
class TestTaxPercentageDecimalApi:
    def test_create_tax_with_decimal_percentage(self, admin_client):
        response = admin_client.post(
            "/api/v1/taxes/",
            json={
                "name": "IVA Ridotta 5.5%",
                "percentage": 5.5,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["percentage"] == 5.5
        assert isinstance(body["percentage"], float)

    def test_get_tax_returns_decimal_percentage(self, admin_client):
        create = admin_client.post(
            "/api/v1/taxes/",
            json={
                "name": "IVA Finlandia 25.5%",
                "percentage": "25.5",
            },
        )
        tax_id = create.json()["id_tax"]

        response = admin_client.get(f"/api/v1/taxes/{tax_id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["percentage"] == 25.5
