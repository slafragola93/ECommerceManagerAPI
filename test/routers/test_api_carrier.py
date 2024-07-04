from src import get_db
from src.main import app
from src.models import CarrierApi
from src.services.auth import get_current_user
from ..utils import client, test_api_carriers, override_get_db, override_get_current_user, TestingSessionLocal, \
    override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

expected_carrier = [
    {
        "id_carrier_api": 1,
        "name": "DHL Italia",
        "account_number": 45856558,
        "site_id": "jHLKJFSHkl_jkfd",
        "national_service": "EHN",
        "international_service": "PPR",
        "is_active": True,
        "api_key": ""
    },
    {
        "id_carrier_api": 2,
        "name": "DHL Francia",
        "account_number": 999999854,
        "site_id": "jbjkb",
        "national_service": "EHN",
        "international_service": "PPR",
        "is_active": False,
        "api_key": ""
    }
]


def test_get_api_carriers(test_api_carriers):
    response = client.get("/api/v1/api_carrier/")

    assert response.status_code == 200
    assert response.json()["carriers"] == expected_carrier
    assert response.json()["total"] == 2


def test_get_api_carrier_by_id(test_api_carriers):
    response = client.get('/api/v1/api_carrier/2')

    # Verifica della risposta
    assert response.status_code == 200

    assert response.json() == expected_carrier[1]

    response = client.get('/api/v1/api_carrier/10')
    assert response.status_code == 404


def test_create_api_carriers(test_api_carriers):
    request_body = {
        "name": "UPS",
        "account_number": 3255,
        "site_id": "Site_ID",
        "national_service": "XRP",
        "international_service": "EMP",
        "password": "xjhsdhisdgi",
        "is_active": 1,
        "api_key": "vvcvxxcvvxvcxvc"
    }

    response = client.post("/api/v1/api_carrier/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 201

    db = TestingSessionLocal()

    carrier = db.query(CarrierApi).filter(CarrierApi.id_carrier_api == 3).first()
    assert carrier is not None

    assert carrier.name == request_body.get('name')
    assert carrier.site_id == request_body.get('site_id')
    assert carrier.national_service == request_body.get('national_service')
    assert carrier.international_service == request_body.get('international_service')
    assert carrier.api_key == request_body.get('api_key')

    request_body = request_body.pop('national_service', None)

    response = client.post("/api/v1/api_carrier/", json=request_body)
    assert response.status_code == 422


def test_delete_api_carrier(test_api_carriers):
    # not found
    response = client.delete('/api/v1/api_carrier/200')
    assert response.status_code == 404

    response = client.delete("/api/v1/api_carrier/2")

    # Verifica della risposta
    assert response.status_code == 200


def test_update_api_carrier(test_api_carriers):
    request_body = {
        "name": "UPS",
        "account_number": 3255,
        "password": "xjhsdhisdgi",
        "site_id": "Site_Id",
        "national_service": "XRP",
        "international_service": "EMP",
        "is_active": True,
        "api_key": "vvcvxxcvvxvcxvc"
    }
    response = client.put("/api/v1/api_carrier/1", json=request_body)
    assert response.status_code == 200

    db = TestingSessionLocal()

    carrier = db.query(CarrierApi).filter(CarrierApi.id_carrier_api == 1).first()
    assert carrier is not None

    assert carrier.name == request_body.get('name')
    assert carrier.account_number == 3255


# TEST SENZA PERMESSI


def test_get_api_carriers_with_user_permissions(test_api_carriers):
    app.dependency_overrides[get_current_user] = override_get_current_user_read_only
    response = client.get("/api/v1/api_carrier/")

    assert response.status_code == 403


def test_get_api_carrier_by_id_with_user_permissions(test_api_carriers):
    response = client.get('/api/v1/api_carrier/2')
    # Verifica della risposta
    assert response.status_code == 403


def test_create_api_carriers_with_user_permissions(test_api_carriers):
    request_body = {
        "name": "UPS",
        "account_number": 3255,
        "site_id": "Site_ID",
        "national_service": "XRP",
        "international_service": "EMP",
        "password": "xjhsdhisdgi",
        "is_active": 1,
        "api_key": "vvcvxxcvvxvcxvc"
    }

    response = client.post("/api/v1/api_carrier/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 403


def test_delete_api_carrier_with_user_permissions(test_api_carriers):
    # not found
    response = client.delete('/api/v1/api_carrier/200')
    assert response.status_code == 403


def test_update_api_carrier_with_user_permissions(test_api_carriers):
    request_body = {
        "name": "UPS",
        "account_number": 3255,
        "password": "xjhsdhisdgi",
        "site_id": "Site_Id",
        "national_service": "XRP",
        "international_service": "EMP",
        "is_active": True,
        "api_key": "vvcvxxcvvxvcxvc"
    }
    response = client.put("/api/v1/api_carrier/1", json=request_body)
    assert response.status_code == 403
    app.dependency_overrides[get_current_user] = override_get_current_user
