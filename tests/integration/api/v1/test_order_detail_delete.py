"""Test integration per `DELETE /api/v1/orders/{order_id}/order_detail/{id_order_detail}`.

Contesto: `OrderService.remove_order_detail` applica ora lo stesso pre-check
fiscale già presente in `OrderDocumentService.remove_articolo` (vedi
`test_preventivo_articoli_delete.py`): se l'`OrderDetail` è già referenziato
da un `FiscalDocumentDetail` (fattura/DDT/nota di credito), la rimozione va
bloccata con **409** e body strutturato
(`error_code="ORDER_DETAIL_HAS_FISCAL_DOCUMENTS"`), invece di far fallire la
DELETE con un 500 generico per violazione FK
(`fiscal_document_details_ibfk_2`).
"""
from datetime import datetime
from decimal import Decimal
from typing import Tuple

import pytest
from fastapi.testclient import TestClient

from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.services.routers.auth_service import get_current_user


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _admin_full_crud_user() -> dict:
    """Bypass permission DB-backed (`role_type=full_crud`)."""
    return {
        "id": 1,
        "username": "admin",
        "role_type": "full_crud",
        "roles": [{"name": "ADMIN", "permissions": ["C", "R", "U", "D"]}],
    }


@pytest.fixture
def admin_full_crud_client(test_app) -> TestClient:
    test_app.dependency_overrides[get_current_user] = _admin_full_crud_user
    return TestClient(test_app)


def _seed_order_with_detail(db_session) -> Tuple[Order, OrderDetail]:
    order = Order(
        id_order_state=1,
        cash_on_delivery=Decimal("0"),
        date_add=datetime.now(),
        total_price_with_tax=Decimal("12.20"),
        products_total_price_net=Decimal("10"),
        products_total_price_with_tax=Decimal("12.20"),
        reference="REF-DETAIL-DEL-001",
    )
    db_session.add(order)
    db_session.flush()

    order_detail = OrderDetail(
        id_order=order.id_order,
        product_name="Prodotto test",
        product_qty=1,
        unit_price_net=Decimal("10"),
        unit_price_with_tax=Decimal("12.20"),
        total_price_net=Decimal("10"),
        total_price_with_tax=Decimal("12.20"),
    )
    db_session.add(order_detail)
    db_session.commit()
    return order, order_detail


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRemoveOrderDetailHappyPath:
    """200 quando l'articolo non è collegato a documenti fiscali."""

    def test_remove_order_detail_without_fiscal_documents_returns_200(
        self, admin_full_crud_client, db_session
    ):
        order, order_detail = _seed_order_with_detail(db_session)
        order_id = order.id_order
        id_order_detail = order_detail.id_order_detail

        response = admin_full_crud_client.delete(
            f"/api/v1/orders/{order_id}/order_detail/{id_order_detail}"
        )

        assert response.status_code == 200, response.text
        assert db_session.query(OrderDetail).filter(
            OrderDetail.id_order_detail == id_order_detail
        ).count() == 0


@pytest.mark.integration
class TestRemoveOrderDetailFiscalDocumentsBlock:
    """409 ORDER_DETAIL_HAS_FISCAL_DOCUMENTS con body strutturato."""

    def test_fiscal_document_detail_blocks_with_409_and_structured_body(
        self, admin_full_crud_client, db_session
    ):
        order, order_detail = _seed_order_with_detail(db_session)
        order_id = order.id_order
        id_order_detail = order_detail.id_order_detail

        fd = FiscalDocument(
            id_order=order_id,
            document_type="invoice",
        )
        db_session.add(fd)
        db_session.flush()

        fdd = FiscalDocumentDetail(
            id_fiscal_document=fd.id_fiscal_document,
            id_order_detail=id_order_detail,
            product_qty=1,
            unit_price_net=Decimal("10"),
            unit_price_with_tax=Decimal("12.20"),
            total_price_net=Decimal("10"),
            total_price_with_tax=Decimal("12.20"),
        )
        db_session.add(fdd)
        db_session.commit()

        response = admin_full_crud_client.delete(
            f"/api/v1/orders/{order_id}/order_detail/{id_order_detail}"
        )

        assert response.status_code == 409, (
            f"OrderDetail collegato a FiscalDocumentDetail deve dare 409. "
            f"Got {response.status_code}: {response.text[:300]}"
        )
        body = response.json()
        assert body.get("error_code") == "ORDER_DETAIL_HAS_FISCAL_DOCUMENTS"
        details = body.get("details", {})
        assert details.get("order_id") == order_id
        assert details.get("id_order_detail") == id_order_detail
        assert details.get("fiscal_document_ids") == [fd.id_fiscal_document]

        # Articolo non cancellato
        assert db_session.query(OrderDetail).filter(
            OrderDetail.id_order_detail == id_order_detail
        ).count() == 1


@pytest.mark.integration
class TestRemoveOrderDetailNotFound:
    """404/400 su order_id o id_order_detail inesistente (ValueError -> handler)."""

    def test_unknown_order_id_returns_404(self, admin_full_crud_client):
        response = admin_full_crud_client.delete(
            "/api/v1/orders/9999999/order_detail/1"
        )
        assert response.status_code == 404, response.text

    def test_unknown_order_detail_id_returns_404(
        self, admin_full_crud_client, db_session
    ):
        order, _ = _seed_order_with_detail(db_session)

        response = admin_full_crud_client.delete(
            f"/api/v1/orders/{order.id_order}/order_detail/9999999"
        )
        assert response.status_code == 404, response.text
