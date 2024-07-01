from src import get_db
from src.main import app
from src.models import Category
from src.services.auth import get_current_user
from ..utils import client, test_category, override_get_db, override_get_current_user, TestingSessionLocal, \
    LIMIT_DEFAULT, override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


def test_get_all_category(test_category):
    """
    Testa il recupero di tutte le categorie disponibili.
    Verifica che lo status code della risposta sia 200 e che i dati restituiti corrispondano
    a quelli attesi, inclusa la presenza della categoria di test inserita.
    """
    response = client.get("/api/v1/categories/")

    # Verifica della risposta
    assert response.status_code == 200

    assert response.json() == {
        "categories": [
            {
                'id_category': 1,
                'id_origin': 702,
                'name': "Climatizzatori",
            }
        ],
        "total": 1,
        "page": 1,
        "limit": LIMIT_DEFAULT
    }




def test_get_category_by_id(test_category):
    """
    Testa il recupero di una categoria specifica tramite il suo ID.

    - Primo test: verifica che una richiesta per un ID inesistente restituisca uno status code 404, indicando che la categoria non è stata trovata.
    - Secondo test: verifica che una richiesta per un ID esistente restituisca i dati corretti della categoria.
    """
    # Not found
    response = client.get("/api/v1/categories/99")

    assert response.status_code == 404

    # Found
    response = client.get("/api/v1/categories/1")
    assert response.json() == {
        'id_category': 1,
        'id_origin': 702,
        'name': "Climatizzatori",
    }


def test_create_category(test_category):
    """
    Testa la creazione di una nuova categoria.

    Verifica che la richiesta POST con i dati della nuova categoria restituisca uno status code 201
    e che la categoria sia effettivamente creata nel database con i dati forniti.
    """
    request_body = {"name": "Scaldabagni"}
    response = client.post("/api/v1/categories/", json=request_body)
    assert response.status_code == 201

    db = TestingSessionLocal()
    model = db.query(Category).filter(Category.id_category == 2).first()
    assert model.id_origin == 0
    assert model.name == request_body.get('name')


def test_delete_category(test_category):
    """
    Testa l'eliminazione di una categoria.

    - Primo test: verifica che una richiesta di eliminazione per un ID inesistente restituisca uno status code 404, indicando che la categoria non è stata trovata e quindi non può essere eliminata.
    - Secondo test: verifica che una richiesta di eliminazione per un ID esistente completi correttamente con uno status code 204,
      e che la categoria sia effettivamente rimossa dal database.
    """
    # Not found
    response = client.delete("/api/v1/categories/99")
    assert response.status_code == 404

    # Found
    response = client.delete("/api/v1/categories/1")
    assert response.status_code == 204


def test_update_category(test_category):
    """
    Testa l'aggiornamento dei dati di una categoria esistente.

    Verifica che una richiesta PUT con i nuovi dati della categoria restituisca uno status code 204,
    e che i dati della categoria nel database siano aggiornati correttamente con i nuovi valori forniti.
    """
    request_body = {"name": "Scaldabagni", "id_origin": 50}
    response = client.put("/api/v1/categories/1", json=request_body)
    assert response.status_code == 204

    db = TestingSessionLocal()
    model = db.query(Category).filter(Category.id_category == 1).first()

    assert model.id_origin == request_body.get('id_origin')
    assert model.name == request_body.get('name')

# TEST CON PERMESSI USER
def test_get_all_category_with_user_permissions(test_category):
    app.dependency_overrides[get_current_user] = override_get_current_user_read_only
    response = client.get("/api/v1/categories/")

    # Verifica della risposta
    assert response.status_code == 200




def test_get_category_by_id_with_user_permissions(test_category):
    response = client.get("/api/v1/categories/99")

    assert response.status_code == 404


def test_create_category_with_user_permissions(test_category):
    request_body = {"name": "Scaldabagni"}
    response = client.post("/api/v1/categories/", json=request_body)
    assert response.status_code == 403


def test_delete_category_with_user_permissions(test_category):

    response = client.delete("/api/v1/categories/99")
    assert response.status_code == 403


def test_update_category_with_user_permissions(test_category):
    request_body = {"name": "Scaldabagni", "id_origin": 50}
    response = client.put("/api/v1/categories/1", json=request_body)
    assert response.status_code == 403

    app.dependency_overrides[get_current_user] = override_get_current_user
