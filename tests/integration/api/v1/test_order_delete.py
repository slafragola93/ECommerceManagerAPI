"""Test integration per `DELETE /api/v1/orders/{id}` (fix bug 500 + nuovo contratto).

Contesto:
- Bug originale (riprodotto live il 2026-05-26 14:16 su ordine 69081):
  IntegrityError MySQL 1451 su `orders_document_ibfk_7` (FK
  `orders_document.id_shipping → shipments.id_shipping` con DELETE RESTRICT).
  Il repo nullava `Order.id_shipping` ma non `OrderDocument.id_shipping`
  prima del DELETE Shipping.
- Fix in `OrderRepository.delete()` step 6b: nulla `OrderDocument.id_shipping`
  per gli shipping in `shipping_ids_to_delete` prima della loro cancellazione.

Contratto FE (FE-ORDER-CANCEL, 2026-05-26):
- DELETE valido in QUALSIASI stato (no piu' restrizione a `id_order_state=1`).
  Per il cambio stato "Annullato" il FE usa `POST /api/v1/orders/bulk-status`.
- FiscalDocument collegati → **409** (non piu' 400) con
  `error_code="ORDER_HAS_FISCAL_DOCUMENTS"` + body strutturato.
- IntegrityError residue → **409** con `error_code="ORDER_DELETE_FK_CONSTRAINT"`
  (difesa in profondita' per FK future non gestite, non per FK gia' note).
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Tuple

import pytest
from fastapi.testclient import TestClient

from src.models.address import Address
from src.models.fiscal_document import FiscalDocument
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.order_document import OrderDocument
from src.models.order_package import OrderPackage
from src.models.shipping import Shipping
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


def _seed_order(
    db_session,
    state: int = 1,
    with_shipping: bool = True,
    n_packages: int = 0,
    n_details: int = 0,
    with_order_document: bool = False,
    with_order_document_sharing_shipping: bool = False,
) -> Tuple[Order, Optional[Shipping], Optional[Address], Optional[OrderDocument]]:
    """Crea Order + relativi collegati per i test DELETE.

    Args:
        with_shipping: crea anche Shipping + Address e li lega all'ordine
        n_packages: numero di OrderPackage da creare
        n_details: numero di OrderDetail da creare
        with_order_document: crea un OrderDocument collegato all'ordine (id_order)
        with_order_document_sharing_shipping: lega OrderDocument.id_shipping
            allo stesso Shipping dell'ordine — riproduce il setup del bug
            originale (la DELETE su Shipping fallirebbe senza il fix 6b).
    """
    address = None
    shipping = None
    if with_shipping:
        address = Address(
            id_country=1, id_customer=1,
            firstname="Mario", lastname="Rossi",
            company="Test SRL", address1="Via Roma 10",
            postcode="00100", city="Roma",
            date_add=date.today(),  # workaround SQLite (Date col func.now())
        )
        db_session.add(address)
        db_session.flush()

        shipping = Shipping(
            id_carrier_api=1,
            id_shipping_state=1,
            tracking="TRK-DEL-001",
            weight=Decimal("1.5"),
            price_tax_incl=Decimal("10"),
            price_tax_excl=Decimal("8.20"),
        )
        db_session.add(shipping)
        db_session.flush()

    order = Order(
        id_shipping=shipping.id_shipping if shipping else None,
        id_address_delivery=address.id_address if address else None,
        id_order_state=state,
        cash_on_delivery=Decimal("0"),
        date_add=datetime.now(),
        total_price_with_tax=Decimal("100"),
        products_total_price_net=Decimal("80"),
        products_total_price_with_tax=Decimal("97.60"),
        reference=f"REF-DEL-{state}",
    )
    db_session.add(order)
    db_session.flush()

    for _ in range(n_packages):
        db_session.add(OrderPackage(id_order=order.id_order))

    for i in range(n_details):
        db_session.add(OrderDetail(
            id_order=order.id_order,
            product_name=f"Prodotto {i+1}",
            product_qty=1,
            unit_price_net=Decimal("10"),
            unit_price_with_tax=Decimal("12.20"),
            total_price_net=Decimal("10"),
            total_price_with_tax=Decimal("12.20"),
        ))

    order_doc = None
    if with_order_document or with_order_document_sharing_shipping:
        order_doc = OrderDocument(
            id_order=order.id_order,
            id_shipping=(
                shipping.id_shipping
                if with_order_document_sharing_shipping and shipping
                else None
            ),
        )
        db_session.add(order_doc)

    db_session.commit()
    return order, shipping, address, order_doc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestOrderDeleteHappyPath:
    """204 No Content nei vari setup di dati collegati."""

    def test_delete_minimal_order_returns_204(
        self, admin_full_crud_client, db_session
    ):
        order, _, _, _ = _seed_order(db_session, with_shipping=False)
        order_id = order.id_order

        response = admin_full_crud_client.delete(f"/api/v1/orders/{order_id}")

        assert response.status_code == 204, response.text
        assert db_session.query(Order).filter(Order.id_order == order_id).count() == 0

    def test_delete_order_in_state_3_returns_204(
        self, admin_full_crud_client, db_session
    ):
        """Stato 3 (Spediti): col VECCHIO contratto sarebbe stato 400.
        Col nuovo contratto FE-ORDER-CANCEL e' 204."""
        order, _, _, _ = _seed_order(db_session, state=3)
        order_id = order.id_order

        response = admin_full_crud_client.delete(f"/api/v1/orders/{order_id}")

        assert response.status_code == 204, (
            f"DELETE deve essere valido in qualsiasi stato (nuovo contratto). "
            f"Got {response.status_code}: {response.text[:300]}"
        )
        assert db_session.query(Order).filter(Order.id_order == order_id).count() == 0

    def test_delete_order_with_packages_and_details_returns_204(
        self, admin_full_crud_client, db_session
    ):
        order, _, _, _ = _seed_order(
            db_session, n_packages=3, n_details=2,
        )
        order_id = order.id_order

        response = admin_full_crud_client.delete(f"/api/v1/orders/{order_id}")

        assert response.status_code == 204, response.text
        assert db_session.query(OrderPackage).filter(
            OrderPackage.id_order == order_id
        ).count() == 0
        assert db_session.query(OrderDetail).filter(
            OrderDetail.id_order == order_id
        ).count() == 0

    def test_delete_order_with_orderdocument_sharing_shipping_returns_204(
        self, admin_full_crud_client, db_session
    ):
        """Riproduce il setup del bug originale (ordine 69081, 2026-05-26 14:16).

        L'OrderDocument condivide `id_shipping` con l'Order: senza il fix 6b
        nel repo, il DELETE FROM shipments solleverebbe IntegrityError 1451
        e l'endpoint risponderebbe 500.
        """
        order, shipping, _, order_doc = _seed_order(
            db_session,
            with_order_document_sharing_shipping=True,
        )
        order_id = order.id_order
        shipping_id = shipping.id_shipping
        order_doc_id = order_doc.id_order_document

        response = admin_full_crud_client.delete(f"/api/v1/orders/{order_id}")

        assert response.status_code == 204, (
            f"Atteso 204 (fix bug OrderDocument.id_shipping). "
            f"Got {response.status_code}: {response.text[:500]}"
        )
        assert db_session.query(Order).filter(Order.id_order == order_id).count() == 0
        assert db_session.query(Shipping).filter(
            Shipping.id_shipping == shipping_id
        ).count() == 0, "Lo shipping doveva essere cancellato col fix"

        # OrderDocument resta (lasciato orphan come da contratto).
        # `expire_all` evita la cache della sessione di test (l'UPDATE
        # `OrderDocument.id_shipping = NULL` e' stato fatto dalla sessione
        # del request override_get_db, distinta da db_session).
        db_session.expire_all()
        order_doc_after = db_session.query(OrderDocument).filter(
            OrderDocument.id_order_document == order_doc_id
        ).first()
        assert order_doc_after is not None, (
            "OrderDocument deve restare nel DB (lasciato orphan)"
        )
        assert order_doc_after.id_shipping is None, (
            "OrderDocument.id_shipping deve essere stato nullato prima del DELETE Shipping"
        )


@pytest.mark.integration
class TestOrderDeleteFiscalDocumentsBlock:
    """409 ORDER_HAS_FISCAL_DOCUMENTS con body strutturato (contratto FE)."""

    def test_fiscal_document_blocks_with_409_and_structured_body(
        self, admin_full_crud_client, db_session
    ):
        order, _, _, _ = _seed_order(db_session, state=1)
        order_id = order.id_order

        fd = FiscalDocument(
            id_order=order_id,
            document_type="invoice",
        )
        db_session.add(fd)
        db_session.commit()

        response = admin_full_crud_client.delete(f"/api/v1/orders/{order_id}")

        assert response.status_code == 409, (
            f"FiscalDocument collegato deve dare 409 (non 400). "
            f"Got {response.status_code}: {response.text[:300]}"
        )
        body = response.json()
        assert body.get("error_code") == "ORDER_HAS_FISCAL_DOCUMENTS"
        details = body.get("details", {})
        assert details.get("order_id") == order_id
        assert details.get("fiscal_documents_count") == 1
        assert details.get("current_state") == 1
        assert details.get("fiscal_document_ids") == [fd.id_fiscal_document]

        # Ordine non cancellato
        assert db_session.query(Order).filter(Order.id_order == order_id).count() == 1


@pytest.mark.integration
class TestOrderDeleteNotFound:
    """404 su order_id inesistente."""

    def test_unknown_order_id_returns_404(
        self, admin_full_crud_client, db_session
    ):
        response = admin_full_crud_client.delete("/api/v1/orders/9999999")
        assert response.status_code == 404, response.text


@pytest.mark.integration
class TestOrderDeleteAuthorization:
    """RBAC: utente senza `orders.delete` → 403 PERMISSION_DENIED."""

    def test_user_without_delete_permission_gets_403(self, test_app, db_session):
        test_app.dependency_overrides[get_current_user] = lambda: {
            "id": 99,
            "username": "noperm",
            "roles": [{"name": "USER", "permissions": ["R"]}],
        }
        client = TestClient(test_app)

        # Anche con order_id casuale: il permesso e' valutato prima del lookup
        response = client.delete("/api/v1/orders/1")

        assert response.status_code == 403
        assert response.json().get("error_code") == "PERMISSION_DENIED"


@pytest.mark.integration
class TestOrderDeleteValidation:
    """Validazione path parameter."""

    def test_negative_order_id_rejected_422(self, admin_full_crud_client):
        response = admin_full_crud_client.delete("/api/v1/orders/-1")
        assert response.status_code == 422

    def test_zero_order_id_rejected_422(self, admin_full_crud_client):
        response = admin_full_crud_client.delete("/api/v1/orders/0")
        assert response.status_code == 422
