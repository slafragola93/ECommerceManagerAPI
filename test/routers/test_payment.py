from src import get_db
from src.main import app
from src.models import Payment
from src.services.auth import get_current_user
from ..utils import client, test_payment, override_get_db, override_get_current_user, TestingSessionLocal, \
    override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

expected_results = [
    {
        "id_payment": 1,
        "name": "Bonifico Bancario",
        "is_complete_payment": False
    },
    {
        "id_payment": 2,
        "name": "Carta Credito",
        "is_complete_payment": True
    },
    {
        "id_payment": 3,
        "name": "Contrassegno",
        "is_complete_payment": False
    }
]


def test_get_payments(test_payment):
    response = client.get("/api/v1/payment/")

    assert response.status_code == 200
    assert response.json()["payments"] == expected_results
    assert response.json()["total"] == 3


def test_get_payment_by_id(test_payment):
    response = client.get('/api/v1/payment/2')

    # Verifica della risposta
    assert response.status_code == 200

    assert response.json() == expected_results[1]

    response = client.get('/api/v1/payment/10')
    assert response.status_code == 404


def test_create_payment(test_payment):
    request_body = {
        "name": "PayPal",
        "is_complete_payment": True
    }

    response = client.post("/api/v1/payment/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 201

    db = TestingSessionLocal()

    payment = db.query(Payment).filter(Payment.id_payment == 4).first()
    assert payment is not None

    assert payment.name == request_body.get('name')


def test_delete_payment(test_payment):
    response = client.delete('/api/v1/payment/200')
    assert response.status_code == 404

    response = client.delete("/api/v1/payment/2")

    # Verifica della risposta
    assert response.status_code == 204


def test_update_payment(test_payment):
    request_body = {
        "name": "Contanti",
        "is_complete_payment": True
    }
    response = client.put("/api/v1/payment/1", json=request_body)
    assert response.status_code == 204

    db = TestingSessionLocal()

    payment = db.query(Payment).filter(Payment.id_payment == 1).first()
    assert payment is not None

    assert payment.name == request_body.get('name')


# TEST CON PERMESSI USER
def test_get_payments_with_user_permissions(test_payment):
    app.dependency_overrides[get_current_user] = override_get_current_user_read_only
    response = client.get("/api/v1/payment/")

    assert response.status_code == 403


def test_get_payment_by_id_with_user_permissions(test_payment):
    response = client.get('/api/v1/payment/2')

    # Verifica della risposta
    assert response.status_code == 403


def test_create_payment_with_user_permissions(test_payment):
    request_body = {
        "name": "PayPal",
        "is_complete_payment": True
    }

    response = client.post("/api/v1/payment/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 403


def test_delete_payment_with_user_permissions(test_payment):
    response = client.delete('/api/v1/payment/200')
    assert response.status_code == 403


def test_update_payment_with_user_permissions(test_payment):
    request_body = {
        "name": "Contanti",
        "is_complete_payment": True
    }
    response = client.put("/api/v1/payment/1", json=request_body)
    assert response.status_code == 403
    app.dependency_overrides[get_current_user] = override_get_current_user

