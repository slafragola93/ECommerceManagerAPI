"""Integration API — documenti nested sull'ordine (returns / invoices / ricevute)."""
from datetime import datetime

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.services.routers.auth_service import get_current_user
from tests.helpers.fiscal_test_helpers import (
    admin_full_crud_user,
    seed_company_info,
    seed_invoice,
    seed_paid_order,
    seed_return,
    seed_tax,
)


@pytest.fixture
def fiscal_admin_client(test_app) -> TestClient:
    test_app.dependency_overrides[get_current_user] = admin_full_crud_user
    return TestClient(test_app)


@pytest.fixture
def tax(db_session):
    return seed_tax(db_session)


@pytest.fixture
def company_info(db_session):
    seed_company_info(db_session)


MISSING_ORDER_ID = 9_999_999


@pytest.mark.integration
class TestOrderAttachedDocumentsAPI:
    def test_empty_nested_lists_return_200(
        self, fiscal_admin_client, db_session, tax, company_info
    ):
        order, _ = seed_paid_order(
            db_session,
            tax,
            reference="API-ATT-EMPTY",
            order_date=datetime(2026, 8, 1, 10, 0, 0),
        )

        for path in ("returns", "invoices", "ricevute"):
            resp = fiscal_admin_client.get(
                f"/api/v1/orders/{order.id_order}/{path}"
            )
            assert resp.status_code == status.HTTP_200_OK, path
            body = resp.json()
            assert body["items"] == []
            assert body["total"] == 0
            assert path in body
            assert body[path] == []

    def test_missing_order_returns_404(self, fiscal_admin_client):
        for path in ("returns", "invoices", "ricevute"):
            resp = fiscal_admin_client.get(
                f"/api/v1/orders/{MISSING_ORDER_ID}/{path}"
            )
            assert resp.status_code == status.HTTP_404_NOT_FOUND, path

    def test_nested_returns_and_invoices(
        self, fiscal_admin_client, db_session, tax
    ):
        order, detail = seed_paid_order(
            db_session,
            tax,
            reference="API-ATT-MIX",
            order_date=datetime(2026, 8, 2, 10, 0, 0),
        )
        return_doc = seed_return(
            db_session,
            tax,
            order,
            detail,
            return_date=datetime(2026, 8, 3, 10, 0, 0),
        )
        invoice = seed_invoice(db_session, order)

        returns_resp = fiscal_admin_client.get(
            f"/api/v1/orders/{order.id_order}/returns"
        )
        assert returns_resp.status_code == status.HTTP_200_OK
        returns_body = returns_resp.json()
        assert returns_body["total"] >= 1
        assert any(
            r["id_fiscal_document"] == return_doc.id_fiscal_document
            for r in returns_body["items"]
        )
        assert returns_body["items"] == returns_body["returns"]

        invoices_resp = fiscal_admin_client.get(
            f"/api/v1/orders/{order.id_order}/invoices"
        )
        assert invoices_resp.status_code == status.HTTP_200_OK
        invoices_body = invoices_resp.json()
        assert invoices_body["total"] >= 1
        assert any(
            i["id_fiscal_document"] == invoice.id_fiscal_document
            for i in invoices_body["items"]
        )
        assert invoices_body["items"] == invoices_body["invoices"]

    def test_nested_ricevute_for_order(
        self, fiscal_admin_client, db_session, tax, company_info
    ):
        order, _ = seed_paid_order(
            db_session,
            tax,
            reference="API-ATT-RIC",
            order_date=datetime(2026, 8, 5, 10, 0, 0),
        )
        create_resp = fiscal_admin_client.post(
            "/api/v1/ricevute",
            json={"id_order": order.id_order, "data_emissione": "2026-08-06"},
        )
        assert create_resp.status_code == status.HTTP_201_CREATED
        created = create_resp.json()

        list_resp = fiscal_admin_client.get(
            f"/api/v1/orders/{order.id_order}/ricevute"
        )
        assert list_resp.status_code == status.HTTP_200_OK
        body = list_resp.json()
        assert body["total"] >= 1
        assert any(
            r["id_ricevuta"] == created["id_ricevuta"] for r in body["items"]
        )
        assert body["items"] == body["ricevute"]

    def test_legacy_invoices_by_order_empty_is_200(
        self, fiscal_admin_client, db_session, tax
    ):
        order, _ = seed_paid_order(
            db_session,
            tax,
            reference="API-ATT-LEG",
            order_date=datetime(2026, 8, 7, 10, 0, 0),
        )
        resp = fiscal_admin_client.get(
            f"/api/v1/fiscal_documents/invoices/order/{order.id_order}"
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == []
