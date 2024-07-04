from src import get_db
from src.main import app
from src.models import Sectional
from src.services.auth import get_current_user
from ..utils import client, test_sectional, override_get_db, override_get_current_user, TestingSessionLocal, \
    override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

expected_results = [
    {
        "id_sectional": 1,
        "name": "p",
    },
    {
        "id_sectional": 2,
        "name": "s",
    },
    {
        "id_sectional": 3,
        "name": "m",
    },
    {
        "id_sectional": 4,
        "name": "n",
    },
    {
        "id_sectional": 5,
        "name": "o",
    }
]


def test_get_sectionals(test_sectional):
    response = client.get("/api/v1/sectional/")

    assert response.status_code == 200
    assert response.json()["sectionals"] == expected_results
    assert response.json()["total"] == 5


def test_get_sectional_by_id(test_sectional):
    response = client.get('/api/v1/sectional/2')

    # Verifica della risposta
    assert response.status_code == 200

    assert response.json() == expected_results[1]

    response = client.get('/api/v1/sectional/10')
    assert response.status_code == 404


def test_create_sectional(test_sectional):
    request_body = {
        "name": "prestashop"
    }

    response = client.post("/api/v1/sectional/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 201

    db = TestingSessionLocal()

    sectional = db.query(Sectional).filter(Sectional.id_sectional == 6).first()
    assert sectional is not None

    assert sectional.name == request_body.get('name')


def test_delete_sectional(test_sectional):
    # not found
    response = client.delete('/api/v1/sectional/200')
    assert response.status_code == 404

    response = client.delete("/api/v1/sectional/2")

    # Verifica della risposta
    assert response.status_code == 204


def test_update_sectional(test_sectional):
    request_body = {
        "name": "Amazon"
    }
    response = client.put("/api/v1/sectional/1", json=request_body)
    assert response.status_code == 204

    db = TestingSessionLocal()

    sectional = db.query(Sectional).filter(Sectional.id_sectional == 1).first()
    assert sectional is not None

    assert sectional.name == request_body.get('name')


# TEST CON PERMESSI USER

def test_get_sectionals_with_user_permissions(test_sectional):
    app.dependency_overrides[get_current_user] = override_get_current_user_read_only
    response = client.get("/api/v1/sectional/")

    assert response.status_code == 403


def test_get_sectional_by_id_with_user_permissions(test_sectional):
    response = client.get('/api/v1/sectional/2')

    # Verifica della risposta
    assert response.status_code == 403


def test_create_sectional_with_user_permissions(test_sectional):
    request_body = {
        "name": "prestashop"
    }

    response = client.post("/api/v1/sectional/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 403


def test_delete_sectional_with_user_permissions(test_sectional):
    # not found
    response = client.delete('/api/v1/sectional/200')
    assert response.status_code == 403


def test_update_sectional_with_user_permissions(test_sectional):
    request_body = {
        "name": "Amazon"
    }
    response = client.put("/api/v1/sectional/1", json=request_body)
    assert response.status_code == 403
    app.dependency_overrides[get_current_user] = override_get_current_user
