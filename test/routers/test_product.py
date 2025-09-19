from src import get_db
from src.main import app
from src.models import Product
from src.services.auth import get_current_user
from ..utils import client, test_product, test_brand, test_category, override_get_db, \
    override_get_current_user, \
    TestingSessionLocal, override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user




def test_get_all_products(test_product, test_brand, test_category):
    """
    Testa la funzionalità di recupero di tutti i prodotti dall'endpoint API.
    Verifica che la risposta includa il prodotto inserito attraverso il fixture di test e
    che i dettagli del prodotto corrispondano a quanto atteso.
    """

    # Verifica della risposta
    response = client.get("/api/v1/products/")

    # Verifica della risposta
    assert response.status_code == 200
    assert response.json()["products"] == [{
        'id_product': 1,
        'id_origin': 0,
        'id_image': None,
        'name': 'Climatizzatore Daikin',
        'sku': '123456',
        'reference': 'ND',
        'type': 'DUAL',
        'weight': 0.0,
        'depth': 0.0,
        'height': 0.0,
        'width': 0.0,
        'category': {
            'id_category': 1,
            'id_origin': 702,
            'name': 'Climatizzatori'
        },
        'brand': {
            'id_brand': 1,
            'id_origin': 1,
            'name': 'Samsung'
        }
    }]


def test_get_products_by_filters(test_product, test_brand, test_category):
    """
    Testa l'endpoint API per il recupero dei prodotti utilizzando vari filtri.
    Prima verifica che la risposta sia 400 per una richiesta con filtro non valido.
    Successivamente, verifica che l'uso di filtri validi restituisca il prodotto corretto.
    """
    # Associazione tag a prodotti
    request_body = {
        "id_product": 1
    }


    response = client.get("/api/v1/products/?product_ids=asasdsd")

    # Verifica della risposta
    assert response.status_code == 400

    response = client.get("/api/v1/products/?categories=1&brands=1&sku=123456&name=Climatizzatore")

    # Verifica della risposta
    assert response.status_code == 200

    assert response.json()["products"] == [{
        'id_product': 1,
        'id_origin': 0,
        'id_image': None,
        'name': 'Climatizzatore Daikin',
        'sku': '123456',
        'reference': 'ND',
        'type': 'DUAL',
        'weight': 0.0,
        'depth': 0.0,
        'height': 0.0,
        'width': 0.0,
        'category': {
            'id_category': 1,
            'id_origin': 702,
            'name': 'Climatizzatori'
        },
        'brand': {
            'id_brand': 1,
            'id_origin': 1,
            'name': 'Samsung'
        }

    }]



def test_get_product_by_id(test_product, test_brand, test_category):
    """
    Testa il recupero di un singolo prodotto tramite il suo ID dall'endpoint API.
    Verifica che la richiesta di un ID inesistente restituisca uno status code 404.
    Per un ID esistente, verifica che i dettagli del prodotto restituito corrispondano a quanto atteso.
    """
    request_body = {
        "id_product": 1
    }

    response = client.get('/api/v1/products/100')
    assert response.status_code == 404

    response = client.get("/api/v1/products/1")

    # Verifica della risposta
    assert response.status_code == 200

    assert response.json() == {
        'id_product': 1,
        'id_origin': 0,
        'id_image': None,
        'name': 'Climatizzatore Daikin',
        'sku': '123456',
        'reference': 'ND',
        'type': 'DUAL',
        'weight': 0.0,
        'depth': 0.0,
        'height': 0.0,
        'width': 0.0,
        'category': {
            'id_category': 1,
            'id_origin': 702,
            'name': 'Climatizzatori'
        },
        'brand': {
            'id_brand': 1,
            'id_origin': 1,
            'name': 'Samsung'
        }
    }


def test_create_product(test_product, test_brand, test_category):
    """
    Testa la funzionalità di creazione di un nuovo prodotto tramite l'endpoint API.
    Invia una richiesta POST con i dettagli di un nuovo prodotto e verifica che
    il prodotto venga creato correttamente nel database, controllando i suoi attributi.
    """

    request_body = {
        "id_origin": 0,
        "id_category": 1,
        "id_brand": 1,
        "name": "Test Prodotto",
        "sku": "Test Sku",
        "type": "DUAL"
    }

    response = client.post("/api/v1/products/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 201

    db = TestingSessionLocal()

    product = db.query(Product).filter(Product.id_product == 2).first()
    assert product is not None

    assert product.id_origin == request_body.get('id_origin')
    assert product.id_category == request_body.get('id_category')
    assert product.id_brand == request_body.get('id_brand')
    assert product.name == request_body.get('name')
    assert product.sku == request_body.get('sku')
    assert product.type == request_body.get('type')


def test_delete_product(test_product, test_brand, test_category):
    """
    Testa l'eliminazione di un prodotto esistente tramite l'endpoint API.
    Prima tenta di eliminare un prodotto con un ID inesistente, verificando che il server risponda con 404.
    Poi elimina un prodotto esistente e verifica che la risposta sia correttamente uno status code 204.
    """

    # not found
    response = client.delete('/api/v1/products/100')
    assert response.status_code == 404

    response = client.delete("/api/v1/products/1")

    # Verifica della risposta
    assert response.status_code == 204


def test_update_product(test_product, test_brand, test_category):
    """
    Testa l'aggiornamento di un prodotto esistente tramite l'endpoint API.
    Invia una richiesta PUT con i nuovi dettagli di un prodotto e verifica che
    le modifiche vengano applicate correttamente, confrontando gli attributi aggiornati nel database.
    """

    request_body = {
        "id_origin": 2,
        "id_category": 2,
        "id_brand": 2,
        "name": "Nome Prodotto Modificato",
        "sku": "Sku Modificato",
        "type": "TRIAL"
    }

    response = client.put("/api/v1/products/1", json=request_body)

    assert response.status_code == 204

    db = TestingSessionLocal()

    product = db.query(Product).filter(Product.id_product == 1).first()
    assert product is not None

    assert product.id_origin == request_body.get('id_origin')
    assert product.id_category == request_body.get('id_category')
    assert product.id_brand == request_body.get('id_brand')
    assert product.name == request_body.get('name')
    assert product.sku == request_body.get('sku')
    assert product.type == request_body.get('type')


# TEST CON PERMESSI USER

def test_get_all_products_with_user_permissions(test_product, test_brand, test_category):
    app.dependency_overrides[get_current_user] = override_get_current_user_read_only
    response = client.get("/api/v1/products/")

    # Verifica della risposta
    assert response.status_code == 200
    assert response.json()["products"] == [{
        'id_product': 1,
        'id_origin': 0,
        'id_image': None,
        'name': 'Climatizzatore Daikin',
        'sku': '123456',
        'reference': 'ND',
        'type': 'DUAL',
        'weight': 0.0,
        'depth': 0.0,
        'height': 0.0,
        'width': 0.0,
        'category': {
            'id_category': 1,
            'id_origin': 702,
            'name': 'Climatizzatori'
        },
        'brand': {
            'id_brand': 1,
            'id_origin': 1,
            'name': 'Samsung'
        }
    }]


def test_get_products_by_filters_with_user_permissions(test_product, test_brand, test_category):
    response = client.get("/api/v1/products/?product_ids=asasdsd")

    # Verifica della risposta
    assert response.status_code == 400

    response = client.get("/api/v1/products/?categories=1&brands=1&sku=123456&name=Climatizzatore")

    # Verifica della risposta
    assert response.status_code == 200

    assert response.json()["products"] == [{
        'id_product': 1,
        'id_origin': 0,
        'id_image': None,
        'name': 'Climatizzatore Daikin',
        'sku': '123456',
        'reference': 'ND',
        'type': 'DUAL',
        'weight': 0.0,
        'depth': 0.0,
        'height': 0.0,
        'width': 0.0,
        'category': {
            'id_category': 1,
            'id_origin': 702,
            'name': 'Climatizzatori'
        },
        'brand': {
            'id_brand': 1,
            'id_origin': 1,
            'name': 'Samsung'
        }
    }]


def test_get_product_by_id_with_user_permissions(test_product, test_brand, test_category):
    response = client.get('/api/v1/products/100')
    assert response.status_code == 404

    response = client.get("/api/v1/products/1")

    # Verifica della risposta
    assert response.status_code == 200

    assert response.json() == {
        'id_product': 1,
        'id_origin': 0,
        'id_image': None,
        'name': 'Climatizzatore Daikin',
        'sku': '123456',
        'reference': 'ND',
        'type': 'DUAL',
        'weight': 0.0,
        'depth': 0.0,
        'height': 0.0,
        'width': 0.0,
        'category': {
            'id_category': 1,
            'id_origin': 702,
            'name': 'Climatizzatori'
        },
        'brand': {
            'id_brand': 1,
            'id_origin': 1,
            'name': 'Samsung'
        }
    }


def test_create_product_with_user_permissions(test_product, test_brand, test_category):
    request_body = {
        "id_origin": 0,
        "id_category": 1,
        "id_brand": 1,
        "name": "Test Prodotto",
        "sku": "Test Sku",
        "type": "DUAL"
    }

    response = client.post("/api/v1/products/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 403


def test_delete_product_with_user_permissions(test_product, test_brand, test_category):
    # not found
    response = client.delete('/api/v1/products/100')
    assert response.status_code == 403


def test_update_product_with_user_permissions(test_product, test_brand, test_category):
    request_body = {
        "id_origin": 2,
        "id_category": 2,
        "id_brand": 2,
        "name": "Nome Prodotto Modificato",
        "sku": "Sku Modificato",
        "type": "TRIAL"
    }

    response = client.put("/api/v1/products/1", json=request_body)

    assert response.status_code == 403
    app.dependency_overrides[get_current_user] = override_get_current_user
