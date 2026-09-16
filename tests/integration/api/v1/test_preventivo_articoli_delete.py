"""Test integration per `DELETE /api/v1/preventivi/articoli/{id_order_detail}`.

Contesto:
- `OrderDocumentService.remove_articolo` (usato da `PreventivoService.remove_articolo`,
  che a sua volta serve l'endpoint DELETE articoli del preventivo) applica ora un
  pre-check fiscale: se l'`OrderDetail` è già referenziato da un
  `FiscalDocumentDetail` (fattura/DDT/nota di credito), la rimozione va bloccata
  con **409** e body strutturato (`error_code="ORDER_DETAIL_HAS_FISCAL_DOCUMENTS"`),
  invece di far fallire la DELETE con un 500 generico per violazione FK
  (`fiscal_document_details_ibfk_2`).
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
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


def _seed_order_detail(db_session) -> OrderDetail:
    order_detail = OrderDetail(
        product_name="Prodotto test",
        product_qty=1,
        unit_price_net=Decimal("10"),
        unit_price_with_tax=Decimal("12.20"),
        total_price_net=Decimal("10"),
        total_price_with_tax=Decimal("12.20"),
    )
    db_session.add(order_detail)
    db_session.commit()
    return order_detail


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRemoveArticoloHappyPath:
    """204 No Content quando l'articolo non è collegato a documenti fiscali."""

    def test_remove_articolo_without_fiscal_documents_returns_204(
        self, admin_full_crud_client, db_session
    ):
        order_detail = _seed_order_detail(db_session)
        id_order_detail = order_detail.id_order_detail

        response = admin_full_crud_client.delete(
            f"/api/v1/preventivi/articoli/{id_order_detail}"
        )

        assert response.status_code == 204, response.text
        assert db_session.query(OrderDetail).filter(
            OrderDetail.id_order_detail == id_order_detail
        ).count() == 0


@pytest.mark.integration
class TestRemoveArticoloFiscalDocumentsBlock:
    """409 ORDER_DETAIL_HAS_FISCAL_DOCUMENTS con body strutturato."""

    def test_fiscal_document_detail_blocks_with_409_and_structured_body(
        self, admin_full_crud_client, db_session
    ):
        order_detail = _seed_order_detail(db_session)
        id_order_detail = order_detail.id_order_detail

        fd = FiscalDocument(
            id_order=1,
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
            f"/api/v1/preventivi/articoli/{id_order_detail}"
        )

        assert response.status_code == 409, (
            f"OrderDetail collegato a FiscalDocumentDetail deve dare 409. "
            f"Got {response.status_code}: {response.text[:300]}"
        )
        body = response.json()
        assert body.get("error_code") == "ORDER_DETAIL_HAS_FISCAL_DOCUMENTS"
        details = body.get("details", {})
        assert details.get("id_order_detail") == id_order_detail
        assert details.get("fiscal_document_ids") == [fd.id_fiscal_document]

        # Articolo non cancellato
        assert db_session.query(OrderDetail).filter(
            OrderDetail.id_order_detail == id_order_detail
        ).count() == 1


@pytest.mark.integration
class TestRemoveArticoloNotFound:
    """404 su id_order_detail inesistente."""

    def test_unknown_order_detail_id_returns_404(
        self, admin_full_crud_client
    ):
        response = admin_full_crud_client.delete(
            "/api/v1/preventivi/articoli/9999999"
        )
        assert response.status_code == 404, response.text
