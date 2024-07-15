from datetime import datetime
from dateutil.relativedelta import relativedelta

from src import get_db
from src.main import app
from src.models import Invoice
from src.services.auth import get_current_user
from ..utils import client, test_invoices, override_get_db, override_get_current_user, TestingSessionLocal, \
    LIMIT_DEFAULT, override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

anno_precedente = datetime.now() - relativedelta(years=1)
due_anni_precedenti = datetime.now() - relativedelta(years=2)

results = [

    {
        "id_invoice": 5,
        "id_order": 1,
        "id_address_delivery": 1,
        "id_address_invoice": 2,
        "invoice_status": "payed",
        "id_customer": 1,
        "payed": True,
        "note": "test note",
        "document_number": 1,
        "date_add": due_anni_precedenti.strftime('%Y-%m-%d')
    },
    {
        "id_invoice": 4,
        "id_order": 1,
        "id_address_delivery": 1,
        "id_address_invoice": 2,
        "invoice_status": "payed",
        "id_customer": 1,
        "payed": True,
        "note": "test note",
        "document_number": 1,
        "date_add": anno_precedente.strftime('%Y-%m-%d')
    },
    {
        "id_invoice": 3,
        "id_order": 1,
        "id_address_delivery": 1,
        "id_address_invoice": 2,
        "invoice_status": "payed",
        "id_customer": 1,
        "payed": True,
        "note": "test note",
        "document_number": 1,
        "date_add": datetime.today().strftime('%Y-%m-%d')
    },
    {
        "id_invoice": 2,
        "id_order": 10,
        "id_address_delivery": 9,
        "id_address_invoice": 2,
        "invoice_status": "payed",
        "id_customer": 5,
        "payed": True,
        "note": "test note",
        "document_number": 2,
        "date_add": datetime.today().strftime('%Y-%m-%d')
    },
    {
        "id_invoice": 1,
        "id_order": 1,
        "id_address_delivery": 1,
        "id_address_invoice": 2,
        "invoice_status": "payed",
        "id_customer": 1,
        "payed": True,
        "note": "test note",
        "document_number": 1,
        "date_add": datetime.today().strftime('%Y-%m-%d')
    }
]


def test_get_all_invoices(test_invoices):
    """
    A function to test the retrieval of all invoices from the API endpoint.
    """
    response = client.get("/api/v1/invoices/")
    # Verifica della risposta
    assert response.status_code == 200
    # test classico
    assert response.json() == {
        "invoices":  results,
        "total": 5,
        "page": 1,
        "limit": LIMIT_DEFAULT
    }

    # test con parametri
    response = client.get("/api/v1/invoices/?payed=true&order_id=1")

    # Verifica della risposta

    assert response.status_code == 200
    results.pop(3)
    assert response.json() == {
        "invoices": results,
        "total": 4,
        "page": 1,
        "limit": LIMIT_DEFAULT
    }
    # test con date
    response = client.get(f"/api/v1/invoices/?date_from=2022-01-01&date_to={due_anni_precedenti.strftime('%Y-%m-%d')}")

    # Verifica della risposta

    assert response.status_code == 200
    assert response.json() == {
        "invoices": [
            {
                "id_invoice": 5,
                "id_order": 1,
                "id_address_delivery": 1,
                "id_address_invoice": 2,
                "invoice_status": "payed",
                "id_customer": 1,
                "payed": True,
                "note": "test note",
                "document_number": 1,
                "date_add": due_anni_precedenti.strftime('%Y-%m-%d')
            }
        ],
        "total": 1,
        "page": 1,
        "limit": LIMIT_DEFAULT
    }

    # test con date
    response = client.get(f"/api/v1/invoices/?date_to={anno_precedente.strftime('%Y-%m-%d')}")

    # Verifica della risposta

    assert response.status_code == 200
    assert response.json() == {
        "invoices": [
            {
                "id_invoice": 5,
                "id_order": 1,
                "id_address_delivery": 1,
                "id_address_invoice": 2,
                "invoice_status": "payed",
                "id_customer": 1,
                "payed": True,
                "note": "test note",
                "document_number": 1,
                "date_add": due_anni_precedenti.strftime('%Y-%m-%d')
            },
            {
                "id_invoice": 4,
                "id_order": 1,
                "id_address_delivery": 1,
                "id_address_invoice": 2,
                "invoice_status": "payed",
                "id_customer": 1,
                "payed": True,
                "note": "test note",
                "document_number": 1,
                "date_add": anno_precedente.strftime('%Y-%m-%d')
            }
        ],
        "total": 2,
        "page": 1,
        "limit": LIMIT_DEFAULT
    }


def test_get_by_id(test_invoices):
    """
    A function to test the retrieval of all invoices from the API endpoint.
    """
    response = client.get("/api/v1/invoices/2")

    # Verifica della risposta
    assert response.status_code == 200
    # test classico
    assert response.json() == {
        "id_invoice": 2,
        "id_order": 10,
        "id_address_delivery": 9,
        "id_address_invoice": 2,
        "invoice_status": "payed",
        "id_customer": 5,
        "payed": True,
        "note": "test note",
        "document_number": 2,
        "date_add": datetime.today().strftime('%Y-%m-%d')
    }


def test_create_invoice(test_invoices):
    # Test classico
    request_body = {
        "id_order": 1,
        "id_address_delivery": 1,
        "id_address_invoice": 2,
        "invoice_status": "payed",
        "id_customer": 1,
        "note": "nota",
        "payed": True
    }
    # Creazione OK
    response = client.post('/api/v1/invoices/', json=request_body)
    assert response.status_code == 201

    db = TestingSessionLocal()

    invoice = db.query(Invoice).filter(Invoice.id_invoice == 6).first()
    assert invoice is not None

    assert invoice.id_order == request_body.get('id_order')
    assert invoice.id_address_delivery == request_body.get('id_address_delivery')
    assert invoice.id_address_invoice == request_body.get('id_address_invoice')
    assert invoice.id_customer == request_body.get('id_customer')
    assert invoice.note == request_body.get('note')
    assert invoice.payed == request_body.get('payed')
    assert invoice.document_number == 3


def test_update_invoice(test_invoices):
    # Test classico
    request_body = {
        "id_order": 10,
        "id_address_delivery": 10,
        "id_address_invoice": 25,
        "invoice_status": "payed",
        "id_customer": 6,
        "note": "testtesttest",
        "payed": False
    }
    # Creazione OK
    response = client.put('/api/v1/invoices/1', json=request_body)
    assert response.status_code == 204

    db = TestingSessionLocal()

    invoice = db.query(Invoice).filter(Invoice.id_invoice == 1).first()

    assert invoice is not None

    assert invoice.id_order == request_body.get('id_order')
    assert invoice.id_address_delivery == request_body.get('id_address_delivery')
    assert invoice.id_address_invoice == request_body.get('id_address_invoice')
    assert invoice.id_customer == request_body.get('id_customer')
    assert invoice.note == request_body.get('note')
    assert invoice.payed == request_body.get('payed')
    assert invoice.document_number == 1


def test_delete_invoice(test_invoices):
    response = client.delete('/api/v1/invoices/1')
    assert response.status_code == 204

    db = TestingSessionLocal()

    invoice = db.query(Invoice).filter(Invoice.id_invoice == 1).first()

    assert invoice is None
