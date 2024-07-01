from datetime import datetime, date
from src import get_db
from src.main import app
from src.models import Shipping
from src.services.auth import get_current_user
from ..utils import client, test_shipping, override_get_db, override_get_current_user, TestingSessionLocal, \
    override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


def test_get_shipping_by_id_shipping(test_shipping):
    response = client.get("/api/v1/shipments/1")

    # Verifica della risposta
    assert response.status_code == 200


# Test creazione shipping
def test_create_shipping(test_shipping):
    request_body = {
        "id_carrier_api": 1,
        "id_shipping_state": 1,
        "id_tax": 3,
        "tracking": "BFJKBASF",
        "weight": 15.0,
        "price_tax_incl": 22.0,
        "price_tax_excl": 19.5,
        "shipping_message": "Prova messaggio"
    }

    # Creazione OK
    response = client.post('/api/v1/shipments/', json=request_body)
    assert response.status_code == 201

    db = TestingSessionLocal()

    model = db.query(Shipping).filter(Shipping.id_shipping == 2).first()

    assert model.id_shipping_state == request_body.get('id_shipping_state')
    assert model.tracking == request_body.get('tracking')
    assert model.price_tax_incl == request_body.get('price_tax_incl')
    assert model.shipping_message == request_body.get('shipping_message')


def test_create_shipping_with_error(test_shipping):
    request_body = {
        "id_shipping_state": 1,
        "id_tax": 3,
        "weight": 15.0,
        "price_tax_incl": 22.0,
        "price_tax_excl": 19.5,
        "shipping_message": "Prova messaggio",
    }

    # Creazione OK
    response = client.post('/api/v1/shipments/', json=request_body)
    assert response.status_code == 422


# Eliminazione customer
def test_delete_shipping(test_shipping):
    # not found
    response = client.delete('/api/v1/shipments/100')
    assert response.status_code == 404

    # found
    response = client.delete('/api/v1/shipments/1')
    assert response.status_code == 204
    db = TestingSessionLocal()
    model = db.query(Shipping).filter(Shipping.id_shipping == 1).first()
    assert model is None


def test_update_shipping(test_shipping):
    request_body = {
        "id_carrier_api": 1,
        "id_shipping_state": 1,
        "id_tax": 1,
        "tracking": "string",
        "weight": 15.0,
        "price_tax_incl": 10.0,
        "price_tax_excl": 8.5,
        "shipping_message": "Prova messaggio modificato",
    }

    # Not found
    response = client.put('/api/v1/shipments/10', json=request_body)
    assert response.status_code == 404

    # Found
    response = client.put('/api/v1/shipments/1', json=request_body)
    assert response.status_code == 204
    db = TestingSessionLocal()
    model = db.query(Shipping).filter(Shipping.id_shipping == 1).first()

    assert model.id_shipping_state == request_body.get('id_shipping_state')
    assert model.id_tax == request_body.get('id_tax')
    assert model.weight == request_body.get('weight')
    assert model.price_tax_incl == request_body.get('price_tax_incl')
    assert model.shipping_message == request_body.get('shipping_message')

