"""Integration API — resi ordine + impatto corrispettivi."""
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.services.routers.auth_service import get_current_user
from tests.helpers.fiscal_test_helpers import (
    admin_full_crud_user,
    seed_paid_order,
    seed_tax,
)


@pytest.fixture
def fiscal_admin_client(test_app) -> TestClient:
    test_app.dependency_overrides[get_current_user] = admin_full_crud_user
    return TestClient(test_app)


@pytest.fixture
def tax(db_session):
    return seed_tax(db_session)


@pytest.mark.integration
class TestOrderReturnsAPI:
    def test_create_list_delete_return_updates_corrispettivi(
        self, fiscal_admin_client, db_session, tax
    ):
        order, detail = seed_paid_order(
            db_session,
            tax,
            reference="API-RET-1",
            order_date=datetime(2026, 7, 20, 10, 0, 0),
        )

        create_resp = fiscal_admin_client.post(
            f"/api/v1/orders/{order.id_order}/returns",
            json={
                "order_details": [
                    {
                        "id_order_detail": detail.id_order_detail,
                        "quantity": 1,
                        "id_tax": tax.id_tax,
                    }
                ],
                "includes_shipping": False,
            },
        )

        assert create_resp.status_code == status.HTTP_201_CREATED
        return_id = create_resp.json()["return_id"]

        list_resp = fiscal_admin_client.get("/api/v1/orders/returns/")
        assert list_resp.status_code == status.HTTP_200_OK
        returns = list_resp.json()["returns"]
        assert any(r["id_fiscal_document"] == return_id for r in returns)

        with_return = fiscal_admin_client.get(
            "/api/v1/corrispettivi/",
            params={"year": 2026, "month": 7},
        ).json()
        assert with_return["month_totals"]["return_count"] >= 1

        delete_resp = fiscal_admin_client.delete(
            f"/api/v1/orders/returns/{return_id}"
        )
        assert delete_resp.status_code == status.HTTP_200_OK

        after_delete = fiscal_admin_client.get(
            "/api/v1/corrispettivi/",
            params={"year": 2026, "month": 7},
        ).json()
        assert after_delete["month_totals"]["return_count"] == 0
        assert Decimal(str(after_delete["month_totals"]["total_with_tax"])) == Decimal(
            "122.00"
        )

    def test_get_return_by_id(self, fiscal_admin_client, db_session, tax):
        order, detail = seed_paid_order(
            db_session,
            tax,
            reference="API-RET-2",
            order_date=datetime(2026, 9, 5, 10, 0, 0),
        )
        created = fiscal_admin_client.post(
            f"/api/v1/orders/{order.id_order}/returns",
            json={
                "order_details": [
                    {
                        "id_order_detail": detail.id_order_detail,
                        "quantity": 1,
                        "id_tax": tax.id_tax,
                    }
                ],
            },
        ).json()

        detail_resp = fiscal_admin_client.get(
            f"/api/v1/orders/returns/get-return-by-id/{created['return_id']}"
        )
        assert detail_resp.status_code == status.HTTP_200_OK
        assert detail_resp.json()["document_type"] == "return"
