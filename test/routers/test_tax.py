from src import get_db
from src.main import app
from src.models import Tax
from src.services.auth import get_current_user
from ..utils import client, test_tax, override_get_db, override_get_current_user, \
    TestingSessionLocal, override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

expected_results = [
    {
        "id_tax": 1,
        "id_country": 4,
        "is_default": 0,
        "name": "Tassa Francia",
        "note": "",
        "percentage": 22,
        "electronic_code": ""
    },
    {
        "id_tax": 2,
        "id_country": 2,
        "is_default": 0,
        "name": "Tassa Italia",
        "note": "Nei sensi dell'articolo 13",
        "percentage": 20,
        "electronic_code": "FR"
    },
    {
        "id_tax": 3,
        "id_country": 1,
        "is_default": 1,
        "name": "Tassa Germania",
        "note": "Nei sensi dell'articolo 13",
        "percentage": 19,
        "electronic_code": ""
    }
]


def test_get_all_taxes(test_tax):
    response = client.get("/api/v1/taxes/")
    # Verifica della risposta
    assert response.status_code == 200
    assert response.json()["taxes"] == expected_results


def test_get_tax_by_id(test_tax):
    response = client.get('/api/v1/taxes/2')

    # Verifica della risposta
    assert response.status_code == 200
    assert response.json() == expected_results[1]

    response = client.get('/api/v1/taxes/5')
    assert response.status_code == 404


def test_create_tax(test_tax):
    request_body = {
        "id_country": 5,
        "is_default": False,
        "name": "Tassa Slovenia",
        "note": "Nei sensi dell'articolo 13",
        "percentage": 16,
        "electronic_code": ""
    }

    response = client.post("/api/v1/taxes/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 201

    db = TestingSessionLocal()

    address = db.query(Tax).filter(Tax.id_tax == 4).first()
    assert address is not None

    assert address.id_country == request_body.get('id_country')
    assert address.is_default == request_body.get('is_default')
    assert address.name == request_body.get('name')
    assert address.percentage == request_body.get('percentage')
    assert address.electronic_code == request_body.get('electronic_code')

    request_body = request_body.pop('name', None)

    response = client.post("/api/v1/taxes/", json=request_body)
    assert response.status_code == 422


def test_delete_tax(test_tax):
    # not found
    response = client.delete('/api/v1/taxes/200')
    assert response.status_code == 404

    response = client.delete("/api/v1/taxes/2")

    # Verifica della risposta
    assert response.status_code == 204


def test_update_tax(test_tax):
    request_body = {
        "id_country": 5,
        "is_default": False,
        "name": "Tassa Slovenia",
        "note": "Nei sensi dell'articolo 13",
        "percentage": 16,
        "electronic_code": ""
    }

    response = client.put("/api/v1/taxes/1", json=request_body)
    assert response.status_code == 204

    db = TestingSessionLocal()

    tax = db.query(Tax).filter(Tax.id_tax == 1).first()
    assert tax is not None

    assert tax.id_country == request_body.get('id_country')
    assert tax.name == request_body.get('name')
    assert tax.id_tax == 1


# TEST CON PERMESSI USER

def test_get_all_taxes_with_user_permissions(test_tax):
    app.dependency_overrides[get_current_user] = override_get_current_user_read_only
    response = client.get("/api/v1/taxes/")
    # Verifica della risposta
    assert response.status_code == 403


def test_get_tax_by_id_with_user_permissions(test_tax):
    response = client.get('/api/v1/taxes/2')

    # Verifica della risposta
    assert response.status_code == 403


def test_create_tax_with_user_permissions(test_tax):
    request_body = {
        "id_country": 5,
        "is_default": False,
        "name": "Tassa Slovenia",
        "note": "Nei sensi dell'articolo 13",
        "percentage": 16,
        "electronic_code": ""
    }

    response = client.post("/api/v1/taxes/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 403


def test_delete_tax_with_user_permissions(test_tax):
    # not found
    response = client.delete('/api/v1/taxes/200')
    assert response.status_code == 403


def test_update_tax_with_user_permissions(test_tax):
    request_body = {
        "id_country": 5,
        "is_default": False,
        "name": "Tassa Slovenia",
        "note": "Nei sensi dell'articolo 13",
        "percentage": 16,
        "electronic_code": ""
    }

    response = client.put("/api/v1/taxes/1", json=request_body)
    assert response.status_code == 403
    app.dependency_overrides[get_current_user] = override_get_current_user