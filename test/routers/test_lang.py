from src import get_db
from src.main import app
from src.models import Lang
from src.services.auth import get_current_user
from ..utils import client, test_lang, override_get_db, override_get_current_user, TestingSessionLocal, \
    override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

expected_results = [
    {
        "id_lang": 1,
        "name": "Italian",
        "iso_code": "it",
    },
    {
        "id_lang": 2,
        "name": "English",
        "iso_code": "en",
    },
    {
        "id_lang": 3,
        "name": "Spanish",
        "iso_code": "es",
    },
    {
        "id_lang": 4,
        "name": "French",
        "iso_code": "fr",
    },
    {
        "id_lang": 5,
        "name": "Deutsch",
        "iso_code": "de",
    }
]


def test_get_languages(test_lang):
    response = client.get("/api/v1/languages/")

    assert response.status_code == 200
    assert response.json()["languages"] == expected_results
    assert response.json()["total"] == 5


def test_get_language_by_id(test_lang):
    response = client.get('/api/v1/languages/4')

    # Verifica della risposta
    assert response.status_code == 200

    assert response.json() == expected_results[3]

    response = client.get('/api/v1/languages/10')
    assert response.status_code == 404


def test_create_languages(test_lang):
    request_body = {
        "name": "Turkish",
        "iso_code": "tk",
    }
    response = client.post("/api/v1/languages/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 201

    db = TestingSessionLocal()

    carrier = db.query(Lang).filter(Lang.id_lang == 6).first()
    assert carrier is not None

    assert carrier.name == request_body.get('name')
    assert carrier.iso_code == request_body.get('iso_code')

    request_body = request_body.pop('name', None)

    response = client.post("/api/v1/languages/", json=request_body)
    assert response.status_code == 422


def test_delete_language(test_lang):
    # not found
    response = client.delete('/api/v1/languages/200')
    assert response.status_code == 404

    response = client.delete("/api/v1/languages/2")

    # Verifica della risposta
    assert response.status_code == 204


def test_update_language(test_lang):
    request_body = {
        "name": "Thai",
        "iso_code": "TL",
    }

    response = client.put("/api/v1/languages/1", json=request_body)

    assert response.status_code == 204

    db = TestingSessionLocal()

    language = db.query(Lang).filter(Lang.id_lang == 1).first()
    assert language is not None

    assert language.name == request_body.get('name')
    assert language.id_lang == 1


# TEST CON PERMESSI USER


def test_get_languages_with_user_permissions(test_lang):
    app.dependency_overrides[get_current_user] = override_get_current_user_read_only
    response = client.get("/api/v1/languages/")

    assert response.status_code == 200


def test_get_language_by_id_with_user_permissions(test_lang):
    response = client.get('/api/v1/languages/4')

    # Verifica della risposta
    assert response.status_code == 200


def test_create_languages_with_user_permissions(test_lang):
    request_body = {
        "name": "Turkish",
        "iso_code": "tk",
    }
    response = client.post("/api/v1/languages/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 403


def test_delete_language_with_user_permissions(test_lang):
    response = client.delete('/api/v1/languages/200')
    assert response.status_code == 403


def test_update_language_with_user_permissions(test_lang):
    request_body = {
        "name": "Thai",
        "iso_code": "TL",
    }

    response = client.put("/api/v1/languages/1", json=request_body)

    assert response.status_code == 403
    app.dependency_overrides[get_current_user] = override_get_current_user
