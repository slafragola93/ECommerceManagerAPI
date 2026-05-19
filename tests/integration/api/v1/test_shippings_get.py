"""
Test per GET /api/v1/shippings/* — verifica che la PK `id_shipping`
sia sempre presente nel body di risposta (convenzione `id_<entity>`
usata su tutte le risorse del dominio).

Vedi ticket: "Fix: GET /api/v1/shippings/{id} non restituisce `id_shipping`".
"""
import pytest
from fastapi import status

from src.models.order import Order
from src.models.shipping import Shipping
from src.schemas.shipping_schema import ShippingResponseSchema
from src.services.routers.auth_service import get_current_user


# ---------------------------------------------------------------------------
# Unit test sullo schema: la PK deve essere serializzata.
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestShippingResponseSchema:
    """Garantisce la presenza di `id_shipping` nello schema di risposta."""

    def test_schema_includes_id_shipping_when_built_from_model(self):
        shipping = Shipping(
            id_shipping=12345,
            id_carrier_api=1,
            id_shipping_state=1,
            id_tax=None,
            tracking=None,
            weight=0.0,
            price_tax_incl=0.0,
            price_tax_excl=0.0,
            customs_value=None,
            shipping_message=None,
        )

        dumped = ShippingResponseSchema.model_validate(shipping).model_dump()

        assert dumped["id_shipping"] == 12345, (
            "ShippingResponseSchema deve esporre `id_shipping`: senza questa "
            "chiave il client Angular non riesce a correlare la PUT con la "
            "subscription della spedizione modificata."
        )
        assert "id_carrier_api" in dumped
        assert "id_shipping_state" in dumped

    def test_schema_id_order_is_optional_and_defaults_to_none(self):
        shipping = Shipping(
            id_shipping=1,
            id_carrier_api=None,
            id_shipping_state=1,
            tracking=None,
            weight=0.0,
            price_tax_incl=0.0,
            price_tax_excl=0.0,
        )

        dumped = ShippingResponseSchema.model_validate(shipping).model_dump()

        assert "id_order" in dumped
        assert dumped["id_order"] is None


# ---------------------------------------------------------------------------
# Test integration: endpoint reali (DB SQLite in-memory).
# ---------------------------------------------------------------------------


def _admin_user_with_full_crud():
    """Ritorna un utente admin con bypass permessi (`role_type=full_crud`)."""
    return {
        "id": 1,
        "username": "admin",
        "role_type": "full_crud",
        "roles": [{"name": "ADMIN", "permissions": ["C", "R", "U", "D"]}],
    }


@pytest.fixture
def admin_full_crud_client(test_app):
    """Client con utente admin che bypassa il controllo permessi DB-backed."""
    from fastapi.testclient import TestClient

    test_app.dependency_overrides[get_current_user] = _admin_user_with_full_crud
    return TestClient(test_app)


@pytest.fixture
def seeded_shipping(db_session):
    """Crea una Shipping di test con un Order collegato."""
    shipping = Shipping(
        id_carrier_api=1,
        id_shipping_state=1,
        tracking=None,
        weight=0.0,
        price_tax_incl=0.0,
        price_tax_excl=0.0,
    )
    db_session.add(shipping)
    db_session.flush()

    order = Order(
        id_shipping=shipping.id_shipping,
        id_order_state=1,
        reference=f"TEST-{shipping.id_shipping}",
    )
    db_session.add(order)
    db_session.commit()

    return shipping, order


@pytest.mark.integration
class TestGetShippingById:
    """GET /api/v1/shippings/{id}"""

    def test_returns_id_shipping_in_body(
        self, admin_full_crud_client, seeded_shipping
    ):
        shipping, order = seeded_shipping

        response = admin_full_crud_client.get(f"/api/v1/shippings/{shipping.id_shipping}")

        assert response.status_code == status.HTTP_200_OK, response.text
        body = response.json()
        assert body["id_shipping"] == shipping.id_shipping, (
            "Il body deve includere `id_shipping`: vedi ticket per impatto "
            "sul client Angular."
        )
        assert body["id_order"] == order.id_order


@pytest.mark.integration
class TestGetAllShippings:
    """GET /api/v1/shippings/?page=&limit="""

    def test_each_item_in_list_has_id_shipping(
        self, admin_full_crud_client, db_session, seeded_shipping
    ):
        # `seeded_shipping` ha già creato uno Shipping. Ne aggiungiamo un altro
        # per esercitare la paginazione.
        extra = Shipping(
            id_carrier_api=1,
            id_shipping_state=1,
            weight=0.0,
            price_tax_incl=0.0,
            price_tax_excl=0.0,
        )
        db_session.add(extra)
        db_session.commit()

        response = admin_full_crud_client.get("/api/v1/shippings/?page=1&limit=50")

        assert response.status_code == status.HTTP_200_OK, response.text
        body = response.json()
        assert "shippings" in body
        assert len(body["shippings"]) >= 2
        for item in body["shippings"]:
            assert "id_shipping" in item, (
                "Ogni elemento di shippings[] deve includere `id_shipping`."
            )
            assert isinstance(item["id_shipping"], int)


@pytest.mark.integration
class TestCreateShipping:
    """POST /api/v1/shippings/"""

    def test_returns_created_object_not_string(self, admin_full_crud_client):
        payload = {
            "id_carrier_api": 1,
            "id_shipping_state": 1,
            "id_tax": 1,
            "tracking": None,
            "weight": 0.5,
            "price_tax_incl": 10.0,
            "price_tax_excl": 8.20,
            "customs_value": None,
            "shipping_message": None,
        }

        response = admin_full_crud_client.post("/api/v1/shippings/", json=payload)

        assert response.status_code == status.HTTP_201_CREATED, response.text
        body = response.json()
        assert isinstance(body, dict), (
            "POST /api/v1/shippings/ deve restituire un oggetto JSON, "
            "non una stringa di conferma."
        )
        assert "id_shipping" in body
        assert isinstance(body["id_shipping"], int)
        assert body["id_carrier_api"] == 1
