"""Integration API — ricevute."""
from datetime import datetime

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.models.ricevuta import Ricevuta
from src.services.routers.auth_service import get_current_user
from tests.helpers.fiscal_test_helpers import (
    admin_full_crud_user,
    seed_company_info,
    seed_paid_order,
    seed_tax,
)


@pytest.fixture
def fiscal_admin_client(test_app) -> TestClient:
    test_app.dependency_overrides[get_current_user] = admin_full_crud_user
    return TestClient(test_app)


@pytest.fixture
def fiscal_user_client(test_app, user_client) -> TestClient:
    return user_client


@pytest.fixture
def tax(db_session):
    return seed_tax(db_session)


@pytest.fixture
def company_info(db_session):
    seed_company_info(db_session)


@pytest.mark.integration
class TestRicevuteAPI:
    def test_create_and_get_ricevuta(
        self, fiscal_admin_client, db_session, tax, company_info
    ):
        order, _ = seed_paid_order(
            db_session,
            tax,
            reference="API-RICE-1",
            order_date=datetime(2026, 8, 1, 10, 0, 0),
        )

        create_resp = fiscal_admin_client.post(
            "/api/v1/ricevute",
            json={"id_order": order.id_order, "data_emissione": "2026-08-05"},
        )

        assert create_resp.status_code == status.HTTP_201_CREATED
        created = create_resp.json()
        assert created["numero"] >= 1
        assert created["anno"] == 2026
        assert created.get("pdf_path") or created.get("pdf_hash")

        detail_resp = fiscal_admin_client.get(
            f"/api/v1/ricevute/{created['id_ricevuta']}"
        )
        assert detail_resp.status_code == status.HTTP_200_OK
        detail = detail_resp.json()
        assert detail["order"]["reference"] == "API-RICE-1"
        assert len(detail["order_details"]) >= 1

    def test_duplicate_ricevuta_blocked(
        self, fiscal_admin_client, db_session, tax, company_info
    ):
        order, _ = seed_paid_order(
            db_session,
            tax,
            reference="API-RICE-DUP",
            order_date=datetime(2026, 8, 2, 10, 0, 0),
        )

        fiscal_admin_client.post(
            "/api/v1/ricevute",
            json={"id_order": order.id_order},
        )
        dup_resp = fiscal_admin_client.post(
            "/api/v1/ricevute",
            json={"id_order": order.id_order},
        )

        assert dup_resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_ricevuta(
        self, fiscal_admin_client, db_session, tax, company_info
    ):
        order, _ = seed_paid_order(
            db_session,
            tax,
            reference="API-RICE-DEL",
            order_date=datetime(2026, 8, 4, 10, 0, 0),
        )
        created = fiscal_admin_client.post(
            "/api/v1/ricevute",
            json={"id_order": order.id_order},
        ).json()

        delete_resp = fiscal_admin_client.delete(
            f"/api/v1/ricevute/{created['id_ricevuta']}"
        )
        assert delete_resp.status_code == status.HTTP_204_NO_CONTENT
        assert (
            db_session.query(Ricevuta)
            .filter(Ricevuta.id_ricevuta == created["id_ricevuta"])
            .count()
            == 0
        )

    def test_get_pdf(
        self, fiscal_admin_client, db_session, tax, company_info
    ):
        order, _ = seed_paid_order(
            db_session,
            tax,
            reference="API-RICE-PDF",
            order_date=datetime(2026, 8, 6, 10, 0, 0),
        )
        created = fiscal_admin_client.post(
            "/api/v1/ricevute",
            json={"id_order": order.id_order},
        ).json()

        pdf_resp = fiscal_admin_client.get(
            f"/api/v1/ricevute/{created['id_ricevuta']}/pdf"
        )

        assert pdf_resp.status_code == status.HTTP_200_OK
        assert pdf_resp.headers["content-type"] == "application/pdf"
        assert pdf_resp.content[:4] == b"%PDF"

    def test_forbidden_without_permissions(self, fiscal_user_client):
        response = fiscal_user_client.get("/api/v1/ricevute")
        assert response.status_code == status.HTTP_403_FORBIDDEN
