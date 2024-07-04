from datetime import datetime
from src import get_db
from src.main import app
from src.models import Customer
from src.services.auth import get_current_user
from ..utils import client, test_customer, override_get_db, override_get_current_user, TestingSessionLocal, \
    LIMIT_DEFAULT, override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


def test_get_all_customers(test_customer):
    """
    A function to test the retrieval of all customers from the API endpoint.
    """
    response = client.get("/api/v1/customers/")

    # Verifica della risposta
    assert response.status_code == 200
    assert response.json() == {
        "customers": [
            {
                'id_customer': 1,
                'id_origin': 0,
                'id_lang': 1,
                'firstname': "Enzo",
                'lastname': "Cristiano",
                'email': 'enzocristiano@elettronew.com',
                'date_add': datetime.today().strftime('%Y-%m-%dT00:00:00')
            }
        ],
        "total": 1,
        "page": 1,
        "limit": LIMIT_DEFAULT
    }

    response = client.get("/api/v1/customers/?id_lang=2,1")

    # Verifica della risposta
    assert response.status_code == 200
    assert response.json() == {
        "customers": [
            {
                'id_customer': 1,
                'id_origin': 0,
                'id_lang': 1,
                'firstname': "Enzo",
                'lastname': "Cristiano",
                'email': 'enzocristiano@elettronew.com',
                'date_add': datetime.today().strftime('%Y-%m-%dT00:00:00')
            }
        ],
        "total": 1,
        "page": 1,
        "limit": LIMIT_DEFAULT
    }


def test_get_customer_by_id_lang(test_customer):
    """
    Get customer by ID and language, and verify the response.
    """
    response = client.get("/api/v1/customers/?id_lang=1")

    # Verifica della risposta
    assert response.status_code == 200
    assert response.json() == {
        "customers": [
            {
                'id_customer': 1,
                'id_origin': 0,
                'id_lang': 1,
                'firstname': "Enzo",
                'lastname': "Cristiano",
                'email': 'enzocristiano@elettronew.com',
                'date_add': datetime.today().strftime('%Y-%m-%dT00:00:00')
            }
        ],
        "total": 1,
        "page": 1,
        "limit": LIMIT_DEFAULT
    }


def test_get_customer_by_id_customer(test_customer):
    """
    Get a customer by their ID and verify the response status code and JSON data.
    """
    response = client.get("/api/v1/customers/1")

    # Verifica della risposta
    assert response.status_code == 200
    assert response.json() == {
        'id_customer': 1,
        'id_origin': 0,
        'id_lang': 1,
        'firstname': "Enzo",
        'lastname': "Cristiano",
        'email': 'enzocristiano@elettronew.com',
        'date_add': datetime.today().strftime('%Y-%m-%dT00:00:00')
    }


# Test creazione customer
def test_create_customer(test_customer):
    """
    A function to test the creation of a customer with the provided test_customer data.
    """
    request_body = {
        "id_origin": 0,
        "id_lang": 3,
        "firstname": "test_firstname",
        "lastname": "test_lastname",
        "email": "test@test.com"
    }

    # Creazione OK
    response = client.post('/api/v1/customers/', json=request_body)
    assert response.status_code == 201
    db = TestingSessionLocal()
    model = db.query(Customer).filter(Customer.id_customer == 2).first()
    assert model.id_origin == request_body.get('id_origin')
    assert model.id_lang == request_body.get('id_lang')
    assert model.firstname == request_body.get('firstname')
    assert model.lastname == request_body.get('lastname')
    assert model.email == request_body.get('email')


def test_create_customer_with_error(test_customer):
    """
    A test function to create a customer with an error using the provided test_customer data.
    """
    request_body = {
        "id_origin": 0,
        "id_lang": 3,
        "email": "test@test.com"
    }

    # Creazione OK
    response = client.post('/api/v1/customers/', json=request_body)
    assert response.status_code == 422

    # test con cliente gia esistente
    request_body = {
        "id_origin": 0,
        "id_lang": 3,
        "firstname": "Ricardo",
        "lastname": "Cotechino",
        "email": "enzocristiano@elettronew.com"
    }
    response = client.post('/api/v1/customers/', json=request_body)
    assert response.status_code == 409


# Eliminazione customer
def test_delete_customer(test_customer):
    """
    A function to test the delete functionality for a customer.

    Parameters:
    test_customer (object): The customer object to be tested.

    Returns:
    None
    """
    # not found
    response = client.delete('/api/v1/customers/100')
    assert response.status_code == 404

    # found
    response = client.delete('/api/v1/customers/1')
    assert response.status_code == 204
    db = TestingSessionLocal()
    model = db.query(Customer).filter(Customer.id_customer == 1).first()
    assert model is None


def test_update_customer(test_customer):
    """
    A function to update a customer's information and verify the changes in the database.

    Parameters:
    test_customer (object): The test customer object to update.

    Returns:
    None
    """
    request_body = {
        "id_origin": 0,
        "id_lang": 3,
        "firstname": "test_firstname",
        "lastname": "test_lastname",
        "email": "test@test.com"
    }

    # Not found
    response = client.put('/api/v1/customers/10', json=request_body)
    assert response.status_code == 404

    # Found
    response = client.put('/api/v1/customers/1', json=request_body)
    assert response.status_code == 204
    db = TestingSessionLocal()
    model = db.query(Customer).filter(Customer.id_customer == 1).first()

    assert model.id_origin == request_body.get('id_origin')
    assert model.id_lang == request_body.get('id_lang')
    assert model.firstname == request_body.get('firstname')
    assert model.lastname == request_body.get('lastname')
    assert model.email == request_body.get('email')


# TEST CON PERMESSI USER

def test_get_all_customers_with_user_permissions(test_customer):
    app.dependency_overrides[get_current_user] = override_get_current_user_read_only
    response = client.get("/api/v1/customers/")

    # Verifica della risposta
    assert response.status_code == 200


def test_get_customer_by_id_lang_with_user_permissions(test_customer):
    """
    Get customer by ID and language, and verify the response.
    """
    response = client.get("/api/v1/customers/?id_lang=1")

    # Verifica della risposta
    assert response.status_code == 200


def test_get_customer_by_id_customer_with_user_permissions(test_customer):
    response = client.get("/api/v1/customers/1")

    # Verifica della risposta
    assert response.status_code == 200
    assert response.json() == {
        'id_customer': 1,
        'id_origin': 0,
        'id_lang': 1,
        'firstname': "Enzo",
        'lastname': "Cristiano",
        'email': 'enzocristiano@elettronew.com',
        'date_add': datetime.today().strftime('%Y-%m-%dT00:00:00')
    }


def test_create_customer_with_user_permissions(test_customer):
    request_body = {
        "id_origin": 0,
        "id_lang": 3,
        "firstname": "test_firstname",
        "lastname": "test_lastname",
        "email": "test@test.com"
    }

    response = client.post('/api/v1/customers/', json=request_body)
    assert response.status_code == 403


def test_create_customer_with_error_with_user_permissions(test_customer):
    request_body = {
        "id_origin": 0,
        "id_lang": 1,
        "firstname": "Giorgio",
        "lastname": "Tirabassi",
        "email": "g.tirabassi@mail.com"
    }

    # Creazione OK
    response = client.post('/api/v1/customers/', json=request_body)
    assert response.status_code == 403


def test_delete_customer_with_user_permissions(test_customer):
    response = client.delete('/api/v1/customers/100')
    assert response.status_code == 403


def test_update_customer_with_user_permissions(test_customer):
    request_body = {
        "id_origin": 0,
        "id_lang": 3,
        "firstname": "test_firstname",
        "lastname": "test_lastname",
        "email": "test@test.com"
    }

    # Not found
    response = client.put('/api/v1/customers/10', json=request_body)
    assert response.status_code == 403
    app.dependency_overrides[get_current_user] = override_get_current_user
