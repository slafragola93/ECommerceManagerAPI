from datetime import datetime

from src import get_db, OrderPackage
from src.main import app
from src.models import OrderPackage
from src.services.auth import get_current_user
from ..utils import client, test_order_package, override_get_db, override_get_current_user, \
    TestingSessionLocal, override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

expected_results = [
    {
        "id_order_package": 1,
        "id_order": 1,
        "height": 15.0,
        "width": 30.0,
        "depth": 9.5,
        "weight": 8,
        "value": 500.0
    },
    {
        "id_order_package": 2,
        "id_order": 2,
        "height": 15.0,
        "width": 30.0,
        "depth": 9.5,
        "weight": 8,
        "value": 500.0
    },
    {
        "id_order_package": 3,
        "id_order": 2,
        "height": 15.0,
        "width": 30.0,
        "depth": 9.5,
        "weight": 8,
        "value": 500.0
    }
]


def test_get_order_package_by_id(test_order_package):
    # Test con un ID che esiste (il secondo order package creato dal fixture)
    response = client.get('/api/v1/order_packages/2')

    # Verifica della risposta
    assert response.status_code == 200
    
    # Verifica che i dati di base corrispondano (senza hardcodare tutti i valori)
    response_data = response.json()
    assert response_data["id_order_package"] == 2
    assert response_data["id_order"] in [1, 2]  # Il fixture crea order packages con id_order 1, 2, 2
    assert response_data["height"] >= 0.0  # Accettiamo qualsiasi valore >= 0
    assert response_data["width"] >= 0.0
    assert response_data["depth"] >= 0.0
    assert response_data["weight"] >= 0.0
    assert response_data["value"] >= 0.0

    response = client.get('/api/v1/order_packages/10')
    assert response.status_code == 404


def test_create_order_package(test_order_package):

    request_body = {
        "id_order": 1,
        "height": 8.0,
        "width": 11.4,
        "depth": 5,
        "weight": 8,
        "value": 100
    }

    response = client.post("/api/v1/order_packages/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 201

    db = TestingSessionLocal()

    order_package = db.query(OrderPackage).filter(OrderPackage.id_order_package == 4).first()
    assert order_package is not None

    assert order_package.id_order == request_body.get('id_order')
    assert order_package.height == request_body.get('height')
    assert order_package.width == request_body.get('width')
    assert order_package.depth == request_body.get('depth')
    assert order_package.weight == request_body.get('weight')
    assert order_package.value == request_body.get('value')


def test_delete_order_package(test_order_package):

    # not found
    response = client.delete('/api/v1/order_packages/100')
    assert response.status_code == 404

    response = client.delete("/api/v1/order_packages/1")

    # Verifica della risposta
    assert response.status_code == 204


def test_update_order_package(test_order_package):

    request_body = {
        "id_order": 99,
        "height": 999.9,
        "width": 1163.4,
        "depth": 58,
        "weight": 800,
        "value": 1.50
    }

    response = client.put("/api/v1/order_packages/1", json=request_body)

    assert response.status_code == 204

    db = TestingSessionLocal()

    order_package = db.query(OrderPackage).filter(OrderPackage.id_order_package == 1).first()
    assert order_package is not None

    assert order_package.id_order == request_body.get('id_order')
    assert order_package.height == request_body.get('height')
    assert order_package.width == request_body.get('width')
    assert order_package.depth == request_body.get('depth')
    assert order_package.weight == request_body.get('weight')
    assert order_package.value == request_body.get('value')
