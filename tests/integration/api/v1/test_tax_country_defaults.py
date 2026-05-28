"""Integration test — /api/v1/taxes/country-defaults (BE-VIES-1)."""
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.models.country import Country
from src.models.tax import Tax
from src.services.routers.auth_service import get_current_user


def _admin_full_crud_user() -> dict:
    return {
        "username": "admin",
        "id": 1,
        "role_type": "full_crud",
        "roles": [{"name": "ADMIN", "permissions": ["C", "R", "U", "D"]}],
    }


def _basic_user() -> dict:
    return {
        "username": "user",
        "id": 2,
        "roles": [{"name": "USER", "permissions": ["R"]}],
    }


@pytest.fixture
def admin_full_crud_client(test_app) -> TestClient:
    test_app.dependency_overrides[get_current_user] = _admin_full_crud_user
    return TestClient(test_app)


@pytest.fixture
def basic_user_client(test_app) -> TestClient:
    test_app.dependency_overrides[get_current_user] = _basic_user
    return TestClient(test_app)


@pytest.fixture
def unauthenticated_client(test_app) -> TestClient:
    from fastapi import HTTPException

    async def _raise_unauthorized():
        raise HTTPException(status_code=401, detail="Utente non autenticato")

    test_app.dependency_overrides[get_current_user] = _raise_unauthorized
    return TestClient(test_app)


@pytest.fixture
def seed_it_default(db_session):
    country = Country(id_origin=1, name="Italy", iso_code="IT")
    db_session.add(country)
    db_session.commit()
    db_session.refresh(country)
    tax = Tax(
        id_country=country.id_country,
        is_default=1,
        name="IVA IT 22%",
        percentage=22,
        code="VATIT",
        electronic_code="",
    )
    db_session.add(tax)
    db_session.commit()
    db_session.refresh(tax)
    return country, tax


@pytest.mark.integration
class TestTaxCountryDefaultsEndpoints:
    def test_list_country_defaults_200(self, admin_full_crud_client, seed_it_default):
        _, tax = seed_it_default
        response = admin_full_crud_client.get("/api/v1/taxes/country-defaults")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["status"] == "success"
        assert body["count"] >= 1
        assert any(item["id_tax"] == tax.id_tax for item in body["data"])

    def test_get_by_iso_200(self, admin_full_crud_client, seed_it_default):
        _, tax = seed_it_default
        response = admin_full_crud_client.get("/api/v1/taxes/country-defaults/IT")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["data"]["id_tax"] == tax.id_tax
        assert body["data"]["percentage"] == 22

    def test_get_by_iso_404(self, admin_full_crud_client, db_session):
        country = Country(id_origin=99, name="France", iso_code="FR")
        db_session.add(country)
        db_session.commit()
        response = admin_full_crud_client.get("/api/v1/taxes/country-defaults/FR")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_set_country_default_200(self, admin_full_crud_client, db_session, seed_it_default):
        country, tax_default = seed_it_default
        tax_other = Tax(
            id_country=country.id_country,
            is_default=0,
            name="IVA IT 10%",
            percentage=10,
            code="VAT10",
        )
        db_session.add(tax_other)
        db_session.commit()
        db_session.refresh(tax_other)

        response = admin_full_crud_client.put(
            f"/api/v1/taxes/{tax_other.id_tax}/set-country-default"
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["status"] == "success"
        assert body["data"]["id_tax"] == tax_other.id_tax
        assert body["data"]["is_default"] == 1

        db_session.expire_all()
        assert db_session.get(Tax, tax_default.id_tax).is_default == 0
        assert db_session.get(Tax, tax_other.id_tax).is_default == 1

    def test_set_country_default_404(self, admin_full_crud_client):
        response = admin_full_crud_client.put(
            "/api/v1/taxes/99999/set-country-default"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_401(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/v1/taxes/country-defaults")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_forbidden_without_full_crud_403(self, basic_user_client):
        response = basic_user_client.get("/api/v1/taxes/country-defaults")
        assert response.status_code == status.HTTP_403_FORBIDDEN
