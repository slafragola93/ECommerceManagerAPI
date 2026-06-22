"""Integration test — electronic_code esteso CODICE - DESCRIZIONE (FE handoff)."""
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.models.country import Country
from src.models.tax import Tax
from src.services.routers.auth_service import get_current_user

EXTENDED_ELECTRONIC_CODE = "N3.1 - Non imponibili - esportazioni"


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
class TestTaxElectronicCodeLength:
    def test_post_accepts_extended_electronic_code(self, admin_client, it_country):
        response = admin_client.post(
            "/api/v1/taxes/",
            json={
                "id_country": it_country.id_country,
                "is_default": 0,
                "name": "Test cod natura esteso",
                "note": "",
                "percentage": 12,
                "electronic_code": EXTENDED_ELECTRONIC_CODE,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["electronic_code"] == EXTENDED_ELECTRONIC_CODE

    def test_put_accepts_extended_electronic_code(
        self, admin_client, it_country, db_session
    ):
        tax = Tax(
            id_country=it_country.id_country,
            is_default=0,
            name="IVA 0% base",
            percentage=0,
            code="N0",
            electronic_code="N3.1",
        )
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        response = admin_client.put(
            f"/api/v1/taxes/{tax.id_tax}",
            json={
                "id_country": it_country.id_country,
                "is_default": 0,
                "name": "IVA 0% base",
                "note": "",
                "percentage": 0,
                "electronic_code": EXTENDED_ELECTRONIC_CODE,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["electronic_code"] == EXTENDED_ELECTRONIC_CODE

    def test_get_and_init_return_full_electronic_code(
        self, admin_client, it_country, db_session
    ):
        tax = Tax(
            id_country=it_country.id_country,
            is_default=0,
            name="IVA Init Extended Code",
            percentage=0,
            code="N31",
            electronic_code=EXTENDED_ELECTRONIC_CODE,
        )
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        get_response = admin_client.get(f"/api/v1/taxes/{tax.id_tax}")
        assert get_response.status_code == status.HTTP_200_OK
        assert get_response.json()["electronic_code"] == EXTENDED_ELECTRONIC_CODE

        init_response = admin_client.get("/api/v1/init/?include=static")
        assert init_response.status_code == status.HTTP_200_OK
        matched = [
            t
            for t in init_response.json()["taxes"]
            if t["name"] == "IVA Init Extended Code"
        ]
        assert matched
        assert matched[0]["electronic_code"] == EXTENDED_ELECTRONIC_CODE

    def test_short_electronic_code_still_valid(self, admin_client, it_country):
        response = admin_client.post(
            "/api/v1/taxes/",
            json={
                "id_country": it_country.id_country,
                "is_default": 0,
                "name": "IVA codice corto",
                "percentage": 22,
                "electronic_code": "N3.1",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["electronic_code"] == "N3.1"
