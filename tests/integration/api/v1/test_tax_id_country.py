"""Integration test — id_country int|null in risposte Tax e init (BE-ALIQ-04)."""
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.models.country import Country
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
def it_country(db_session):
    country = Country(id_origin=1, name="Italy", iso_code="IT")
    db_session.add(country)
    db_session.commit()
    db_session.refresh(country)
    return country


@pytest.mark.integration
class TestTaxIdCountryApiResponses:
    def test_get_tax_returns_int_id_country(self, admin_client, it_country, db_session):
        tax = Tax(
            id_country=it_country.id_country,
            is_default=0,
            name="IVA IT 22%",
            percentage=22,
            code="IT22",
        )
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        response = admin_client.get(f"/api/v1/taxes/{tax.id_tax}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id_country"] == it_country.id_country
        assert isinstance(body["id_country"], int)

    def test_get_global_tax_returns_null_id_country(self, admin_client, db_session):
        tax = Tax(
            id_country=None,
            is_default=1,
            name="IVA Global Default",
            percentage=22,
            code="GLB",
        )
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        response = admin_client.get(f"/api/v1/taxes/{tax.id_tax}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id_country"] is None

    def test_post_accepts_string_id_country_and_returns_int(
        self, admin_client, it_country
    ):
        response = admin_client.post(
            "/api/v1/taxes/",
            json={
                "name": "IVA String Country",
                "percentage": 22,
                "id_country": str(it_country.id_country),
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["id_country"] == it_country.id_country
        assert isinstance(body["id_country"], int)

    def test_init_static_taxes_id_country_types(self, admin_client, it_country, db_session):
        tax = Tax(
            id_country=it_country.id_country,
            is_default=0,
            name="IVA Init Test",
            percentage=22,
            code="INIT",
        )
        db_session.add(tax)
        db_session.commit()

        response = admin_client.get("/api/v1/init/?include=static")
        assert response.status_code == status.HTTP_200_OK
        taxes = response.json()["taxes"]
        matched = [t for t in taxes if t["name"] == "IVA Init Test"]
        assert matched
        assert isinstance(matched[0]["id_country"], int)

        global_tax = Tax(
            id_country=None,
            is_default=0,
            name="IVA Init Global",
            percentage=0,
            code="INIT0",
        )
        db_session.add(global_tax)
        db_session.commit()

        response = admin_client.get("/api/v1/init/?include=static")
        taxes = response.json()["taxes"]
        matched_global = [t for t in taxes if t["name"] == "IVA Init Global"]
        assert matched_global
        assert matched_global[0]["id_country"] is None
