from src import get_db
from src.main import app
from src.models import Configuration
from src.services.auth import get_current_user
from ..utils import client, test_configuration, override_get_db, override_get_current_user, TestingSessionLocal, \
    override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

expected_results = [
    {
        "id_configuration": 1,
        "id_lang": 1,
        "name": "ECOMMERCE_PS",
        "value": "1",
    },
    {
        "id_configuration": 2,
        "id_lang": 5,
        "name": "SCRIPT_DEBUG",
        "value": "1"
    },
    {
        "id_configuration": 3,
        "id_lang": 0,
        "name": "Tipo Caricamento",
        "value": "Cron"
    }
]


def test_get_configs(test_configuration):
    response = client.get("/api/v1/configs/")

    assert response.status_code == 200
    assert response.json()["configurations"] == expected_results
    assert response.json()["total"] == 3


def test_get_config_by_id(test_configuration):
    response = client.get('/api/v1/configs/2')

    # Verifica della risposta
    assert response.status_code == 200

    assert response.json() == expected_results[1]

    response = client.get('/api/v1/configs/10')
    assert response.status_code == 404


def test_create_config(test_configuration):
    request_body = {
        "id_lang": 0,
        "name": "TEST_CONFIG",
        "value": "98273"
    }

    response = client.post("/api/v1/configs/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 201

    db = TestingSessionLocal()

    config = db.query(Configuration).filter(Configuration.id_configuration == 4).first()
    assert config is not None

    assert config.id_configuration == 4
    assert config.name == request_body.get('name')

    request_body = request_body.pop('name', None)

    response = client.post("/api/v1/configs/", json=request_body)
    assert response.status_code == 422


def test_delete_config(test_configuration):
    # not found
    response = client.delete('/api/v1/configs/200')
    assert response.status_code == 404

    response = client.delete("/api/v1/configs/2")

    # Verifica della risposta
    assert response.status_code == 204


def test_update_config(test_configuration):

    request_body = {
        "name": "SCRIPT_DEBUG",
        "value": "0"
    }
    response = client.put("/api/v1/configs/2", json=request_body)
    assert response.status_code == 204

    db = TestingSessionLocal()

    config = db.query(Configuration).filter(Configuration.id_configuration == 2).first()
    assert config is not None

    assert config.name == request_body.get('name')
    assert config.id_configuration == 2
    assert config.id_lang == 5

# TEST CON PERMESSI USER

def test_get_configs_with_user_permissions(test_configuration):
    app.dependency_overrides[get_current_user] = override_get_current_user_read_only
    response = client.get("/api/v1/configs/")

    assert response.status_code == 403


def test_get_config_by_id_with_user_permissions(test_configuration):
    response = client.get('/api/v1/configs/2')

    # Verifica della risposta
    assert response.status_code == 403


def test_create_config_with_user_permissions(test_configuration):
    request_body = {
        "id_lang": 0,
        "name": "TEST_CONFIG",
        "value": "98273"
    }

    response = client.post("/api/v1/configs/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 403


def test_delete_config_with_user_permissions(test_configuration):
    # not found
    response = client.delete('/api/v1/configs/200')
    assert response.status_code == 403



def test_update_config_with_user_permissions(test_configuration):

    request_body = {
        "name": "SCRIPT_DEBUG",
        "value": "0"
    }
    response = client.put("/api/v1/configs/2", json=request_body)
    assert response.status_code == 403
    app.dependency_overrides[get_current_user] = override_get_current_user