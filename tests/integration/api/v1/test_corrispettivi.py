"""Integration API — corrispettivi."""
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.services.routers.auth_service import get_current_user
from tests.helpers.fiscal_test_helpers import (
    admin_full_crud_user,
    seed_paid_order,
    seed_return,
    seed_tax,
)


@pytest.fixture
def fiscal_admin_client(test_app) -> TestClient:
    test_app.dependency_overrides[get_current_user] = admin_full_crud_user
    return TestClient(test_app)


@pytest.fixture
def fiscal_user_client(test_app, user_client) -> TestClient:
    """Utente senza bypass permessi granulari."""
    return user_client


@pytest.fixture
def tax(db_session):
    return seed_tax(db_session)


@pytest.mark.integration
class TestCorrispettiviAPI:
    def test_get_daily_summary_empty_month(self, fiscal_admin_client):
        response = fiscal_admin_client.get(
            "/api/v1/corrispettivi/",
            params={"year": 2099, "month": 1},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["year"] == 2099
        assert data["month"] == 1
        assert data["month_totals"]["total_with_tax"] == 0
        assert data["month_totals"]["order_count"] == 0

    def test_get_daily_summary_with_movement(self, fiscal_admin_client, db_session, tax):
        order, detail = seed_paid_order(
            db_session,
            tax,
            reference="API-CORR-1",
            order_date=datetime(2026, 8, 3, 10, 0, 0),
        )
        seed_return(
            db_session,
            tax,
            order,
            detail,
            return_date=datetime(2026, 8, 10, 12, 0, 0),
        )

        response = fiscal_admin_client.get(
            "/api/v1/corrispettivi/",
            params={"year": 2026, "month": 8},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["month_totals"]["total_with_tax"] != 0 or data["month_totals"]["return_count"] > 0
        assert any(d["date"] == "2026-08-03" for d in data["days"])

    def test_get_riepilogo_shape(self, fiscal_admin_client, db_session, tax):
        seed_paid_order(
            db_session,
            tax,
            reference="API-RIEP",
            order_date=datetime(2026, 8, 5, 10, 0, 0),
        )

        response = fiscal_admin_client.get(
            "/api/v1/corrispettivi/riepilogo",
            params={"year": 2026, "month": 8},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "columns" in data
        assert "rows" in data
        assert data["month_totals"]["row_total"] > 0

    def test_export_zip(self, fiscal_admin_client, db_session, tax):
        seed_paid_order(
            db_session,
            tax,
            reference="API-EXP",
            order_date=datetime(2026, 8, 7, 10, 0, 0),
        )

        response = fiscal_admin_client.post(
            "/api/v1/corrispettivi/export",
            json={"year": 2026, "month": 8},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/zip"
        assert len(response.content) > 100

    def test_get_giorno_riepilogo(self, fiscal_admin_client, db_session, tax):
        seed_paid_order(
            db_session,
            tax,
            reference="API-GIORNO-1",
            order_date=datetime(2026, 8, 1, 10, 0, 0),
        )
        seed_paid_order(
            db_session,
            tax,
            reference="API-GIORNO-15",
            order_date=datetime(2026, 8, 15, 10, 0, 0),
        )

        response = fiscal_admin_client.get(
            "/api/v1/corrispettivi/giorno/riepilogo",
            params={"year": 2026, "month": 8, "day": 1},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["day"] == 1
        assert len(data["rows"]) == 1
        assert data["rows"][0]["day"] == 1

    def test_export_giorno_zip(self, fiscal_admin_client, db_session, tax):
        seed_paid_order(
            db_session,
            tax,
            reference="API-EXP-GIORNO",
            order_date=datetime(2026, 8, 3, 10, 0, 0),
        )

        response = fiscal_admin_client.post(
            "/api/v1/corrispettivi/giorno/export",
            json={"year": 2026, "month": 8, "day": 3},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "Registro_2026-08-03.zip" in response.headers.get(
            "content-disposition", ""
        )
        assert len(response.content) > 100

    def test_invalid_day_returns_422(self, fiscal_admin_client):
        response = fiscal_admin_client.get(
            "/api/v1/corrispettivi/giorno",
            params={"year": 2026, "month": 2, "day": 30},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_forbidden_without_permissions(self, fiscal_user_client):
        response = fiscal_user_client.get(
            "/api/v1/corrispettivi/",
            params={"year": 2026, "month": 8},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
