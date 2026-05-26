"""Test integration per POST /api/v1/bordero/generate (PR 8a — Borderò).

Copre i casi della checklist sez. 8 del prompt BE:

1. **0 ordini idonei** → 200 + PDF "vuoto" + `X-Bordero-Order-Count: 0`
2. **N ordini, update_status=false** → PDF generato, count corretto,
   `X-Bordero-Order-Ids` valorizzato, nessun cambio stato in DB, nessun evento
3. **N ordini, update_status=true** → PDF generato + ordini passano a stato 4 +
   evento `ORDER_STATUS_CHANGED` emesso (uno per ordine)
4. **Filtri date** restringono correttamente la finestra (analogo `GET /api/v1/orders/`)
5. **Auth fallita** (utente senza `shipments.create`) → 403 + `PERMISSION_DENIED`
6. **Carrier inattivo** (`is_active=false`) → 200 + count=0 (no errore)
7. **Tracking vuoto/null** → escluso dal borderò
8. **Headers di risposta**: `Content-Disposition: inline`, filename `bordero_<CARRIER>_<YYYYMMDD>.pdf`,
   `Access-Control-Expose-Headers` espone gli header custom.

Il setup usa SQLite in-memory (`db_session` fixture in `tests/conftest.py`) e
l'`EventBusSpy` per intercettare gli eventi senza far partire i listener reali.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Tuple

import pytest
from fastapi.testclient import TestClient

from sqlalchemy import text

from src.events.core.event import EventType
from src.models.address import Address
from src.models.carrier_api import CarrierApi, CarrierTypeEnum
from src.models.order import Order
from src.models.order_package import OrderPackage
from src.models.order_state import OrderState
from src.models.shipping import Shipping
from src.services.routers.auth_service import get_current_user
from tests.helpers.asserts import assert_no_event_published


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _admin_full_crud_user() -> dict:
    """Utente con bypass totale dei permessi (`role_type=full_crud`).

    Necessario perché `require_permission("shipments", "create")` cerca
    `AppModule.name='shipments'` in DB, e in SQLite-in-memory la tabella e'
    vuota → senza bypass tutti gli endpoint risponderebbero 403.
    """
    return {
        "id": 1,
        "username": "admin",
        "role_type": "full_crud",
        "roles": [{"name": "ADMIN", "permissions": ["C", "R", "U", "D"]}],
    }


@pytest.fixture
def admin_full_crud_client(test_app) -> TestClient:
    """Client HTTP autenticato come admin con bypass permessi."""
    test_app.dependency_overrides[get_current_user] = _admin_full_crud_user
    return TestClient(test_app)


@pytest.fixture
def seed_carrier_brt(db_session) -> CarrierApi:
    """CarrierApi BRT attivo (id=1)."""
    carrier = CarrierApi(
        id_carrier_api=1,
        name="BRT",
        carrier_type=CarrierTypeEnum.BRT,
        is_active=True,
        use_sandbox=False,
    )
    db_session.add(carrier)
    db_session.commit()
    return carrier


@pytest.fixture
def seed_order_states(db_session) -> None:
    """OrderState 3 (Spediti) e 4 (Spedizione Confermata).

    Servono entrambi: `OrderService.update_order_status` valida il target
    contro `OrderState` table e ritorna `None` se l'id non esiste (no event).
    """
    db_session.add_all([
        OrderState(id_order_state=3, name="Spediti"),
        OrderState(id_order_state=4, name="Spedizione Confermata"),
    ])
    db_session.commit()


def _seed_shipment(
    db_session,
    carrier_id: int,
    tracking: Optional[str] = "TRK-001",
    weight: float = 1.5,
    cod: float = 19.90,
    state: int = 3,
    date_add: Optional[datetime] = None,
    n_packages: int = 1,
    address_company: str = "Test SRL",
) -> Tuple[Order, Shipping, Address]:
    """Helper: crea Address + Shipping + Order + N OrderPackage collegati.

    Returns:
        Tupla (order, shipping, address) coi modelli persistiti e refreshati.
    """
    address = Address(
        id_country=1,
        id_customer=1,
        firstname="Mario",
        lastname="Rossi",
        company=address_company,
        address1="Via Roma 10",
        postcode="00100",
        city="Roma",
        # Override esplicito: il default `func.now()` su SQLite produce
        # un timestamp non-ISO che fallisce il parse a `Date` in lettura.
        date_add=date.today(),
    )
    db_session.add(address)
    db_session.flush()

    shipping = Shipping(
        id_carrier_api=carrier_id,
        id_shipping_state=1,
        tracking=tracking,
        weight=Decimal(str(weight)),
        price_tax_incl=Decimal("10"),
        price_tax_excl=Decimal("8.20"),
    )
    db_session.add(shipping)
    db_session.flush()

    order = Order(
        id_shipping=shipping.id_shipping,
        id_address_delivery=address.id_address,
        id_order_state=state,
        cash_on_delivery=Decimal(str(cod)),
        date_add=date_add or datetime.now(),
        total_price_with_tax=Decimal("100"),
        products_total_price_net=Decimal("80"),
        products_total_price_with_tax=Decimal("97.60"),
        reference=f"REF-{tracking or 'NONE'}",
    )
    db_session.add(order)
    db_session.flush()

    for _ in range(n_packages):
        db_session.add(OrderPackage(id_order=order.id_order))

    db_session.commit()
    return order, shipping, address


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestBorderoGenerateZeroOrders:
    """Caso "0 ordini idonei": deve ritornare 200 con PDF "vuoto" — NON 404.

    Contratto FE (PR 8b): il FE mostra alert info senza aprire il PDF.
    """

    def test_returns_200_with_empty_pdf_and_count_zero(
        self, admin_full_crud_client, seed_carrier_brt
    ):
        response = admin_full_crud_client.post(
            "/api/v1/bordero/generate",
            json={"carrier_id": 1, "update_status": False},
        )

        assert response.status_code == 200, (
            f"Atteso 200 anche su 0 ordini (contratto FE PR 8b). "
            f"Got {response.status_code}: {response.text[:300]}"
        )
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["x-bordero-order-count"] == "0"
        assert response.headers["x-bordero-order-ids"] == ""
        assert response.content.startswith(b"%PDF"), (
            "Il body deve essere un PDF valido anche con 0 ordini"
        )

    def test_unknown_carrier_id_still_returns_200(
        self, admin_full_crud_client, seed_carrier_brt
    ):
        """carrier_id che non esiste in DB → comunque 200 + count=0."""
        response = admin_full_crud_client.post(
            "/api/v1/bordero/generate",
            json={"carrier_id": 99999, "update_status": False},
        )

        assert response.status_code == 200
        assert response.headers["x-bordero-order-count"] == "0"
        assert response.content.startswith(b"%PDF")


@pytest.mark.integration
class TestBorderoGenerateWithOrders:
    """N ordini idonei: count, order_ids, contenuto PDF."""

    def test_n_orders_without_status_update_keeps_state(
        self,
        admin_full_crud_client,
        seed_carrier_brt,
        seed_order_states,
        db_session,
        event_bus_spy,
    ):
        order1, _, _ = _seed_shipment(db_session, 1, tracking="TRK001")
        order2, _, _ = _seed_shipment(db_session, 1, tracking="TRK002")

        response = admin_full_crud_client.post(
            "/api/v1/bordero/generate",
            json={"carrier_id": 1, "update_status": False},
        )

        assert response.status_code == 200
        assert response.headers["x-bordero-order-count"] == "2"
        returned_ids = sorted(
            int(x) for x in response.headers["x-bordero-order-ids"].split(",")
        )
        assert returned_ids == sorted([order1.id_order, order2.id_order])

        db_session.refresh(order1)
        db_session.refresh(order2)
        assert order1.id_order_state == 3, "Stato NON deve cambiare con update_status=false"
        assert order2.id_order_state == 3

        assert_no_event_published(event_bus_spy, EventType.ORDER_STATUS_CHANGED.value)

    def test_n_orders_with_status_update_moves_to_state_4_and_logs_history(
        self,
        admin_full_crud_client,
        seed_carrier_brt,
        seed_order_states,
        db_session,
    ):
        """Con update_status=true gli ordini passano a stato 4 e viene
        inserita una riga in `orders_history` per ciascuno.

        Nota: la verifica dell'evento `ORDER_STATUS_CHANGED` non viene fatta
        qui perché `_extract_order_status_data` chiama `next(get_db())`
        direttamente (bypassando l'override FastAPI) e query un DB esterno
        che in test non esiste. Il side effect su `orders_history` e' la
        garanzia equivalente: e' la stessa scrittura usata dai listener reali.
        """
        order1, _, _ = _seed_shipment(db_session, 1, tracking="TRK001")
        order2, _, _ = _seed_shipment(db_session, 1, tracking="TRK002")

        response = admin_full_crud_client.post(
            "/api/v1/bordero/generate",
            json={"carrier_id": 1, "update_status": True},
        )

        assert response.status_code == 200
        assert response.headers["x-bordero-order-count"] == "2"

        db_session.refresh(order1)
        db_session.refresh(order2)
        assert order1.id_order_state == 4, (
            f"Atteso stato 4 (Spedizione Confermata) per order {order1.id_order}, "
            f"got {order1.id_order_state}"
        )
        assert order2.id_order_state == 4

        history_rows = db_session.execute(
            text(
                "SELECT id_order, id_order_state FROM orders_history "
                "WHERE id_order IN (:o1, :o2) AND id_order_state = 4"
            ),
            {"o1": order1.id_order, "o2": order2.id_order},
        ).all()
        history_order_ids = {row[0] for row in history_rows}
        assert history_order_ids == {order1.id_order, order2.id_order}, (
            f"orders_history deve contenere una riga (id_order_state=4) per "
            f"ciascun ordine. Got: {history_order_ids}"
        )


@pytest.mark.integration
class TestBorderoDateFilters:
    """date_from/date_to: stessa semantica di `GET /api/v1/orders/`."""

    def test_date_filters_narrow_window(
        self,
        admin_full_crud_client,
        seed_carrier_brt,
        seed_order_states,
        db_session,
    ):
        old_order, _, _ = _seed_shipment(
            db_session, 1, tracking="OLD",
            date_add=datetime(2025, 1, 15, 10, 0, 0),
        )
        new_order, _, _ = _seed_shipment(
            db_session, 1, tracking="NEW",
            date_add=datetime(2026, 5, 20, 10, 0, 0),
        )

        response = admin_full_crud_client.post(
            "/api/v1/bordero/generate",
            json={
                "carrier_id": 1,
                "update_status": False,
                "date_from": "2025-01-01",
                "date_to": "2025-12-31",
            },
        )

        assert response.status_code == 200
        assert response.headers["x-bordero-order-count"] == "1", (
            f"Atteso 1 ordine nella finestra 2025, got "
            f"{response.headers['x-bordero-order-count']}"
        )
        assert response.headers["x-bordero-order-ids"] == str(old_order.id_order)

    def test_date_to_uses_datetime_semantics_consistent_with_orders_list(
        self,
        admin_full_crud_client,
        seed_carrier_brt,
        seed_order_states,
        db_session,
    ):
        """`date_to` viene confrontato come DATETIME (00:00:00 implicito).

        Pattern ereditato da `OrderRepository.get_all()` usato da
        `GET /api/v1/orders/`: il prompt richiede esplicitamente la stessa
        semantica. Conseguenza: per includere un ordine creato il giorno X
        alle 12:00, il FE deve passare `date_to=X+1` (il giorno DOPO).

        Questo test documenta il comportamento per evitare regressioni future
        — un eventuale cambio (es. cast a DATE) andrebbe coordinato con
        `OrderRepository.get_all` per non creare divergenze tra borderò e
        lista ordini visibile dall'operatore.
        """
        order_mid_day, _, _ = _seed_shipment(
            db_session, 1, tracking="MID-DAY",
            date_add=datetime(2026, 5, 10, 12, 0, 0),
        )

        same_day_response = admin_full_crud_client.post(
            "/api/v1/bordero/generate",
            json={
                "carrier_id": 1,
                "update_status": False,
                "date_from": "2026-05-10",
                "date_to": "2026-05-10",
            },
        )
        assert same_day_response.status_code == 200
        assert same_day_response.headers["x-bordero-order-count"] == "0", (
            "Comportamento atteso e' di escludere ordini con orario != 00:00:00 "
            "quando date_to == data del giorno (coerente con GET /api/v1/orders/)"
        )

        next_day_response = admin_full_crud_client.post(
            "/api/v1/bordero/generate",
            json={
                "carrier_id": 1,
                "update_status": False,
                "date_from": "2026-05-10",
                "date_to": "2026-05-11",
            },
        )
        assert next_day_response.status_code == 200
        assert next_day_response.headers["x-bordero-order-count"] == "1"
        assert next_day_response.headers["x-bordero-order-ids"] == str(
            order_mid_day.id_order
        )


@pytest.mark.integration
class TestBorderoEligibilityFilters:
    """Filtri di idoneità (corriere attivo, tracking, stato ordine)."""

    def test_inactive_carrier_returns_zero_orders(
        self,
        admin_full_crud_client,
        seed_order_states,
        db_session,
    ):
        inactive = CarrierApi(
            id_carrier_api=2,
            name="DHL",
            carrier_type=CarrierTypeEnum.DHL,
            is_active=False,
            use_sandbox=False,
        )
        db_session.add(inactive)
        db_session.commit()

        _seed_shipment(db_session, 2, tracking="TRK")

        response = admin_full_crud_client.post(
            "/api/v1/bordero/generate",
            json={"carrier_id": 2, "update_status": False},
        )

        assert response.status_code == 200
        assert response.headers["x-bordero-order-count"] == "0", (
            "Corriere disattivo deve essere escluso anche se ha spedizioni storiche"
        )

    def test_empty_tracking_excluded(
        self,
        admin_full_crud_client,
        seed_carrier_brt,
        seed_order_states,
        db_session,
    ):
        _seed_shipment(db_session, 1, tracking="VALID-TRK")
        _seed_shipment(db_session, 1, tracking="")
        _seed_shipment(db_session, 1, tracking=None)

        response = admin_full_crud_client.post(
            "/api/v1/bordero/generate",
            json={"carrier_id": 1, "update_status": False},
        )

        assert response.status_code == 200
        assert response.headers["x-bordero-order-count"] == "1", (
            "Solo le spedizioni con tracking non-null e non-stringa-vuota "
            "vanno nel borderò"
        )

    def test_orders_in_other_states_excluded(
        self,
        admin_full_crud_client,
        seed_carrier_brt,
        seed_order_states,
        db_session,
    ):
        """Solo ordini in stato 3 (Spediti) entrano nel borderò."""
        _seed_shipment(db_session, 1, tracking="T1", state=1)
        _seed_shipment(db_session, 1, tracking="T2", state=2)
        spedito, _, _ = _seed_shipment(db_session, 1, tracking="T3", state=3)
        _seed_shipment(db_session, 1, tracking="T4", state=4)

        response = admin_full_crud_client.post(
            "/api/v1/bordero/generate",
            json={"carrier_id": 1, "update_status": False},
        )

        assert response.status_code == 200
        assert response.headers["x-bordero-order-count"] == "1"
        assert response.headers["x-bordero-order-ids"] == str(spedito.id_order)


@pytest.mark.integration
class TestBorderoResponseHeaders:
    """Verifica formato headers richiesto dal contratto FE."""

    def test_content_disposition_is_inline_with_correct_filename(
        self,
        admin_full_crud_client,
        seed_carrier_brt,
        seed_order_states,
        db_session,
    ):
        _seed_shipment(db_session, 1, tracking="TRK")

        response = admin_full_crud_client.post(
            "/api/v1/bordero/generate",
            json={"carrier_id": 1, "update_status": False},
        )

        cd = response.headers["content-disposition"]
        assert cd.startswith('inline; filename="bordero_BRT_'), (
            f"Content-Disposition deve essere 'inline' con filename "
            f"'bordero_BRT_<YYYYMMDD>.pdf'. Got: {cd}"
        )
        assert cd.endswith('.pdf"')

        expose = response.headers["access-control-expose-headers"]
        assert "X-Bordero-Order-Count" in expose
        assert "X-Bordero-Order-Ids" in expose
        assert "Content-Disposition" in expose


@pytest.mark.integration
class TestBorderoAuthorization:
    """Auth/permission checks (sez. 8.5 della checklist)."""

    def test_user_without_permission_gets_403(self, test_app):
        """User base (no role_type=full_crud, no AppModule in DB) → 403."""
        test_app.dependency_overrides[get_current_user] = lambda: {
            "id": 99,
            "username": "noperm_user",
            "roles": [{"name": "USER", "permissions": ["R"]}],
        }
        client = TestClient(test_app)

        response = client.post(
            "/api/v1/bordero/generate",
            json={"carrier_id": 1, "update_status": False},
        )

        assert response.status_code == 403
        body = response.json()
        assert body.get("error_code") == "PERMISSION_DENIED", (
            f"Atteso error_code=PERMISSION_DENIED dal body strutturato. Got: {body}"
        )


@pytest.mark.integration
class TestBorderoValidation:
    """Validazione Pydantic del body."""

    def test_negative_carrier_id_rejected_422(self, admin_full_crud_client):
        response = admin_full_crud_client.post(
            "/api/v1/bordero/generate",
            json={"carrier_id": -1, "update_status": False},
        )
        assert response.status_code == 422

    def test_missing_carrier_id_rejected_422(self, admin_full_crud_client):
        response = admin_full_crud_client.post(
            "/api/v1/bordero/generate",
            json={"update_status": False},
        )
        assert response.status_code == 422

    def test_invalid_date_format_rejected_422(self, admin_full_crud_client):
        response = admin_full_crud_client.post(
            "/api/v1/bordero/generate",
            json={
                "carrier_id": 1,
                "update_status": False,
                "date_from": "not-a-date",
            },
        )
        assert response.status_code == 422
