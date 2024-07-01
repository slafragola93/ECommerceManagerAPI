from src import get_db
from src.main import app
from src.models import Brand
from src.services.auth import get_current_user
from ..utils import client, test_brand, override_get_db, override_get_current_user, TestingSessionLocal, LIMIT_DEFAULT, \
    override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


def test_get_all_brands(test_brand):
    """
    Testa la restituzione di tutti i marchi disponibili.
    Verifica che lo status code della risposta sia 200 e che i dati restituiti corrispondano
    a quelli attesi, inclusa la presenza del marchio di test inserito.
    """
    response = client.get("/api/v1/brands/")

    # Verifica della risposta
    assert response.status_code == 200
    assert response.json() == {
        "brands": [
            {
                'id_brand': 1,
                'id_origin': 1,
                'name': "Samsung",
            }
        ],
        "total": 1,
        "page": 1,
        "limit": LIMIT_DEFAULT
    }


def test_get_brand_by_id(test_brand):
    """
    Testa il recupero di un marchio specifico tramite il suo ID.

    - Primo test: verifica che una richiesta per un ID inesistente restituisca uno status code 404.
    - Secondo test: verifica che una richiesta per un ID esistente restituisca i dati corretti del marchio.
    """
    # Not found
    response = client.get("/api/v1/brands/99")

    assert response.status_code == 404

    # Found
    response = client.get("/api/v1/brands/1")
    assert response.json() == {
        'id_brand': 1,
        'id_origin': 1,
        'name': "Samsung",
    }


def test_create_brand(test_brand):
    """
    Testa la creazione di un nuovo marchio.

    Verifica che la richiesta POST con i dati del nuovo marchio restituisca uno status code 201
    e che il marchio sia effettivamente creato nel database con i dati forniti.
    """
    request_body = {"name": "Apple", "id_origin": 10}
    response = client.post("/api/v1/brands/", json=request_body)
    assert response.status_code == 201

    db = TestingSessionLocal()
    model = db.query(Brand).filter(Brand.id_brand == 2).first()
    assert model.id_origin == request_body.get('id_origin')
    assert model.name == request_body.get('name')


def test_delete_brand(test_brand):
    """
    Testa l'eliminazione di un marchio.

    - Primo test: verifica che una richiesta di eliminazione per un ID inesistente restituisca uno status code 404.
    - Secondo test: verifica che una richiesta di eliminazione per un ID esistente completi correttamente con uno status code 204
     e che il marchio sia effettivamente rimosso dal database.
    """
    # Not found
    response = client.delete("/api/v1/brands/99")
    assert response.status_code == 404

    # Found
    response = client.delete("/api/v1/brands/1")
    assert response.status_code == 204


def test_update_brand(test_brand):
    """
    Testa l'aggiornamento dei dati di un marchio esistente.

    Verifica che una richiesta PUT con i nuovi dati del marchio restituisca uno status code 204
    e che i dati del marchio nel database siano aggiornati correttamente.
    """
    # Not found
    response = client.put("/api/v1/brands/99")
    assert response.status_code == 422

    request_body = {"name": "Apple", "id_origin": 10}
    response = client.put("/api/v1/brands/1", json=request_body)
    assert response.status_code == 204

    db = TestingSessionLocal()
    model = db.query(Brand).filter(Brand.id_brand == 1).first()

    assert model.id_origin == request_body.get('id_origin')
    assert model.name == request_body.get('name')


# TEST CON PERMESSI USER


def test_get_all_brands_with_user_permissions(test_brand):
    app.dependency_overrides[get_current_user] = override_get_current_user_read_only
    response = client.get("/api/v1/brands/")

    # Verifica della risposta
    assert response.status_code == 200


def test_get_brand_by_id_with_user_permissions(test_brand):
    response = client.get("/api/v1/brands/1")

    assert response.status_code == 200


def test_create_brand_with_user_permissions(test_brand):
    request_body = {"name": "Apple", "id_origin": 10}
    response = client.post("/api/v1/brands/", json=request_body)
    assert response.status_code == 403


def test_delete_brand_with_user_permissions(test_brand):
    response = client.delete("/api/v1/brands/1")
    assert response.status_code == 403


def test_update_brand_with_user_permissions(test_brand):
    request_body = {"name": "Apple", "id_origin": 10}
    response = client.put("/api/v1/brands/1", json=request_body)
    assert response.status_code == 403
    app.dependency_overrides[get_current_user] = override_get_current_user
