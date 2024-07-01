from datetime import datetime

from src import get_db
from src.main import app
from src.models import Carrier
from src.services.auth import get_current_user
from ..utils import client, test_carriers, override_get_db, override_get_current_user, TestingSessionLocal, \
    override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

expected_carrier = [
    {
        "id_carrier": 1,
        "id_origin": 10,
        "name": "Fedex",
    },
    {
        "id_carrier": 2,
        "id_origin": 20,
        "name": "DHL",
    },
    {
        "id_carrier": 3,
        "id_origin": 21,
        "name": "UPS",
    },
    {
        "id_carrier": 4,
        "id_origin": 22,
        "name": "Mondial Relay",
    }
]


def test_get_carriers(test_carriers):
    response = client.get("/api/v1/carriers/")

    assert response.status_code == 200
    assert response.json()["carriers"] == expected_carrier
    assert response.json()["total"] == 4


def test_get_carriers_by_filters(test_carriers):
    response = client.get("/api/v1/carriers/?carrier_name=ABC")
    assert response.status_code == 404

    response = client.get("/api/v1/carriers/?carrier_name=dhl&origin_ids=20,21,22")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["carriers"][0] == expected_carrier[1]


def test_get_carrier_by_id(test_carriers):
    response = client.get('/api/v1/carriers/4')

    # Verifica della risposta
    assert response.status_code == 200

    assert response.json() == expected_carrier[3]

    response = client.get('/api/v1/carriers/10')
    assert response.status_code == 404


def test_create_carriers(test_carriers):
    request_body = {
        "id_origin": 0,
        "name": "Poste Italiane"
    }

    response = client.post("/api/v1/carriers/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 201

    db = TestingSessionLocal()

    carrier = db.query(Carrier).filter(Carrier.id_carrier == 5).first()
    assert carrier is not None

    assert carrier.id_origin == request_body.get('id_origin')
    assert carrier.name == request_body.get('name')

    request_body = request_body.pop('name', None)

    response = client.post("/api/v1/carriers/", json=request_body)
    assert response.status_code == 422


def test_delete_carrier(test_carriers):
    # not found
    response = client.delete('/api/v1/carriers/200')
    assert response.status_code == 404

    response = client.delete("/api/v1/carriers/2")

    # Verifica della risposta
    assert response.status_code == 200


def test_update_carrier(test_carriers):
    request_body = {
        "id_origin": 0,
        "name": "Poste Italiane",
    }

    response = client.put("/api/v1/carriers/1", json=request_body)
    assert response.status_code == 200

    db = TestingSessionLocal()

    carrier = db.query(Carrier).filter(Carrier.id_carrier == 1).first()
    assert carrier is not None

    assert carrier.name == request_body.get('name')
    assert carrier.id_carrier == 1


# TEST CON PERMESSI USER


def test_get_carriers_with_user_permissions(test_carriers):
    app.dependency_overrides[get_current_user] = override_get_current_user_read_only
    response = client.get("/api/v1/carriers/")

    assert response.status_code == 200


def test_get_carriers_by_filters_with_user_permissions(test_carriers):
    response = client.get("/api/v1/carriers/?carrier_name=ABC")
    assert response.status_code == 404

    response = client.get("/api/v1/carriers/?carrier_name=dhl&origin_ids=20,21,22")

    assert response.status_code == 200


def test_get_carrier_by_id_with_user_permissions(test_carriers):
    response = client.get('/api/v1/carriers/4')

    # Verifica della risposta
    assert response.status_code == 200


def test_create_carriers_with_user_permissions(test_carriers):
    request_body = {
        "id_origin": 0,
        "name": "Poste Italiane"
    }

    response = client.post("/api/v1/carriers/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 403


def test_delete_carrier_with_user_permissions(test_carriers):
    # not found
    response = client.delete('/api/v1/carriers/200')
    assert response.status_code == 403


def test_update_carrier_with_user_permissions(test_carriers):
    request_body = {
        "id_origin": 0,
        "name": "Poste Italiane",
    }

    response = client.put("/api/v1/carriers/1", json=request_body)
    assert response.status_code == 403
    app.dependency_overrides[get_current_user] = override_get_current_user
