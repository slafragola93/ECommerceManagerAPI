"""
Test per endpoints Fiscal Documents (Fatture e Note di Credito)
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, date

from src.main import app
from src.database import Base, get_db
from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.customer import Customer
from src.models.address import Address
from src.models.country import Country
from src.models.tax import Tax
from src.models.user import User
from src.models.role import Role

# Database di test
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_fiscal_documents.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Crea database di test e sessione"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Client FastAPI con database di test"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_token(db_session):
    """Crea utente di test e genera token"""
    # Crea role
    role = Role(id_role=1, name="admin", permissions="CRUD")
    db_session.add(role)
    db_session.commit()
    
    # Crea user
    from src.services.auth import create_access_token
    from datetime import timedelta
    
    user = User(
        id_user=1,
        username="testuser",
        email="test@test.com",
        firstname="Test",
        lastname="User",
        password="hashed_password"
    )
    user.roles.append(role)  # Usa relationship invece di id_role
    db_session.add(user)
    db_session.commit()
    
    # Genera token
    token = create_access_token(
        username=user.username,
        user_id=user.id_user,
        roles=[role],
        expires_delta=timedelta(hours=1)
    )
    
    return token


@pytest.fixture(scope="function")
def test_data(db_session):
    """Crea dati di test: country, customer, address, order, order_details, tax"""
    # Country Italia
    italy = Country(id_country=1, name="Italia", iso_code="IT")
    db_session.add(italy)
    
    # Country estero
    france = Country(id_country=2, name="Francia", iso_code="FR")
    db_session.add(france)
    db_session.commit()
    
    # Customer
    customer = Customer(
        id_customer=1,
        firstname="Mario",
        lastname="Rossi",
        email="mario.rossi@test.com",
        date_add=date.today()  # Evita problemi formato SQLite
    )
    db_session.add(customer)
    db_session.commit()
    
    # Address Italia
    address_it = Address(
        id_address=1,
        id_customer=1,
        id_country=1,
        firstname="Mario",
        lastname="Rossi",
        company="Rossi SRL",
        address1="Via Roma 123",
        city="Napoli",
        postcode="80100",
        state="Napoli",
        vat="IT12345678901",
        dni="RSSMRA80A01F839X",
        pec="mario@pec.it",
        sdi="0000000",
        date_add=date.today()  # Evita problemi formato SQLite
    )
    db_session.add(address_it)
    
    # Address Francia (per test fatture non elettroniche)
    address_fr = Address(
        id_address=2,
        id_customer=1,
        id_country=2,
        firstname="Mario",
        lastname="Rossi",
        address1="Rue de Paris 456",
        city="Paris",
        postcode="75001",
        state="Paris",
        date_add=date.today()  # Evita problemi formato SQLite
    )
    db_session.add(address_fr)
    db_session.commit()
    
    # Tax
    tax = Tax(
        id_tax=1,
        name="IVA 22%",
        percentage=22.0,
        electronic_code=""
    )
    db_session.add(tax)
    db_session.commit()
    
    # Order Italia
    order_it = Order(
        id_order=1,
        id_customer=1,
        id_address_invoice=1,
        id_address_delivery=1,
        reference="ORD001",
        total_price=644.10,
        total_weight=5.0
    )
    db_session.add(order_it)
    
    # Order Francia
    order_fr = Order(
        id_order=2,
        id_customer=1,
        id_address_invoice=2,
        id_address_delivery=2,
        reference="ORD002",
        total_price=500.00,
        total_weight=3.0
    )
    db_session.add(order_fr)
    db_session.commit()
    
    # OrderDetails per Order Italia
    order_detail_1 = OrderDetail(
        id_order_detail=1,
        id_order=1,
        id_product=100,
        product_name="Climatizzatore Daikin 12000 BTU",
        product_reference="DAIKIN-12K",
        product_qty=3,
        product_price=155.033,
        product_weight=2.0,
        id_tax=1,
        reduction_percent=0.0,
        reduction_amount=0.0
    )
    
    order_detail_2 = OrderDetail(
        id_order_detail=2,
        id_order=1,
        id_product=101,
        product_name="Kit installazione",
        product_reference="KIT-INST-001",
        product_qty=2,
        product_price=89.50,
        product_weight=0.5,
        id_tax=1,
        reduction_percent=0.0,
        reduction_amount=0.0
    )
    
    db_session.add_all([order_detail_1, order_detail_2])
    db_session.commit()
    
    return {
        'italy': italy,
        'france': france,
        'customer': customer,
        'address_it': address_it,
        'address_fr': address_fr,
        'tax': tax,
        'order_it': order_it,
        'order_fr': order_fr,
        'order_detail_1': order_detail_1,
        'order_detail_2': order_detail_2
    }


# ==================== TEST CREAZIONE FATTURE ====================

def test_create_invoice_electronic_success(client, db_session, test_data, auth_token):
    """Test creazione fattura elettronica per ordine italiano"""
    response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={
            "id_order": test_data['order_it'].id_order,
            "is_electronic": True
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    
    # Verifica dati fattura
    assert data['document_type'] == 'invoice'
    assert data['tipo_documento_fe'] == 'TD01'
    assert data['is_electronic'] is True
    assert data['status'] == 'pending'
    assert data['document_number'] == '000001'  # Primo numero
    assert data['total_amount'] == test_data['order_it'].total_price
    
    # Verifica che siano stati creati i details
    details = db_session.query(FiscalDocumentDetail).filter(
        FiscalDocumentDetail.id_fiscal_document == data['id_fiscal_document']
    ).all()
    
    assert len(details) == 2  # 2 OrderDetail
    assert details[0].id_order_detail == 1
    assert details[0].quantity == 3
    assert details[1].id_order_detail == 2
    assert details[1].quantity == 2


def test_create_invoice_non_electronic_success(client, db_session, test_data, auth_token):
    """Test creazione fattura non elettronica per ordine estero"""
    response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={
            "id_order": test_data['order_fr'].id_order,
            "is_electronic": False
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    
    assert data['document_type'] == 'invoice'
    assert data['tipo_documento_fe'] is None  # Non elettronica
    assert data['is_electronic'] is False
    assert data['document_number'] is None  # Non ha numero sequenziale


def test_create_invoice_electronic_foreign_address_error(client, db_session, test_data, auth_token):
    """Test errore creazione fattura elettronica per indirizzo estero"""
    response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={
            "id_order": test_data['order_fr'].id_order,
            "is_electronic": True  # Errore: indirizzo francese
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 400
    assert "solo per indirizzi italiani" in response.json()['detail']


def test_create_multiple_invoices_same_order(client, db_session, test_data, auth_token):
    """Test creazione multiple fatture per stesso ordine"""
    # Prima fattura
    response1 = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response1.status_code == 201
    invoice1_number = response1.json()['document_number']
    
    # Seconda fattura sullo stesso ordine
    response2 = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response2.status_code == 201
    invoice2_number = response2.json()['document_number']
    
    # Verifica numerazione sequenziale
    assert invoice2_number == '000002'
    assert invoice1_number == '000001'


# ==================== TEST NOTE DI CREDITO ====================

def test_create_credit_note_total_success(client, db_session, test_data, auth_token):
    """Test creazione nota di credito totale"""
    # Prima crea fattura
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    
    # Crea nota credito totale
    response = client.post(
        "/api/v1/fiscal-documents/credit-notes",
        json={
            "id_invoice": invoice_id,
            "reason": "Reso merce completo",
            "is_partial": False,
            "is_electronic": True
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    
    assert data['document_type'] == 'credit_note'
    assert data['tipo_documento_fe'] == 'TD04'
    assert data['id_fiscal_document_ref'] == invoice_id
    assert data['credit_note_reason'] == "Reso merce completo"
    assert data['is_partial'] is False
    
    # Verifica importo = somma articoli fattura
    invoice_details = db_session.query(FiscalDocumentDetail).filter(
        FiscalDocumentDetail.id_fiscal_document == invoice_id
    ).all()
    expected_amount = sum(d.total_amount for d in invoice_details)
    assert data['total_amount'] == expected_amount


def test_create_credit_note_partial_success(client, db_session, test_data, auth_token):
    """Test creazione nota di credito parziale"""
    # Crea fattura
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    
    # Crea nota credito parziale (solo 1 climatizzatore su 3)
    response = client.post(
        "/api/v1/fiscal-documents/credit-notes",
        json={
            "id_invoice": invoice_id,
            "reason": "Reso parziale - articolo difettoso",
            "is_partial": True,
            "is_electronic": True,
            "items": [
                {
                    "id_order_detail": test_data['order_detail_1'].id_order_detail,
                    "quantity": 1,  # 1 su 3
                    "unit_price": 155.033
                }
            ]
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    
    assert data['document_type'] == 'credit_note'
    assert data['is_partial'] is True
    assert data['total_amount'] == 155.033  # Solo 1 unità
    
    # Verifica details
    assert len(data['details']) == 1
    assert data['details'][0]['id_order_detail'] == test_data['order_detail_1'].id_order_detail
    assert data['details'][0]['quantity'] == 1


def test_create_credit_note_invalid_order_detail(client, db_session, test_data, auth_token):
    """Test errore nota credito con order_detail non nella fattura"""
    # Crea fattura
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    
    # Prova a stornare articolo NON nella fattura
    response = client.post(
        "/api/v1/fiscal-documents/credit-notes",
        json={
            "id_invoice": invoice_id,
            "reason": "Test",
            "is_partial": True,
            "is_electronic": True,
            "items": [
                {
                    "id_order_detail": 999,  # Non esiste
                    "quantity": 1,
                    "unit_price": 100
                }
            ]
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 400
    assert "non presente nella fattura" in response.json()['detail']


def test_create_credit_note_quantity_exceeds_invoice(client, db_session, test_data, auth_token):
    """Test errore nota credito con quantità superiore a quella fatturata"""
    # Crea fattura
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    
    # Prova a stornare più di quanto fatturato
    response = client.post(
        "/api/v1/fiscal-documents/credit-notes",
        json={
            "id_invoice": invoice_id,
            "reason": "Test",
            "is_partial": True,
            "is_electronic": True,
            "items": [
                {
                    "id_order_detail": test_data['order_detail_1'].id_order_detail,
                    "quantity": 10,  # Fatturato: 3, richiesto: 10
                    "unit_price": 155.033
                }
            ]
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 400
    assert "superiore a quella fatturata" in response.json()['detail']


def test_create_credit_note_for_non_electronic_invoice(client, db_session, test_data, auth_token):
    """Test creazione nota credito non elettronica per fattura non elettronica"""
    # Skip: L'ordine Francia non ha OrderDetails nella fixture
    # TODO: Aggiungere OrderDetails per order_fr
    pytest.skip("Order Francia non ha OrderDetails - da implementare fixture completa")


# ==================== TEST NUMERAZIONE SEQUENZIALE ====================

def test_sequential_numbering_same_year(client, db_session, test_data, auth_token):
    """Test numerazione sequenziale nello stesso anno"""
    # Crea 3 fatture
    for i in range(3):
        response = client.post(
            "/api/v1/fiscal-documents/invoices",
            json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 201
        assert response.json()['document_number'] == f"{i+1:06d}"


def test_sequential_numbering_separate_for_credit_notes(client, db_session, test_data, auth_token):
    """Test numerazione sequenziale separata per fatture e note credito"""
    # Crea fattura
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    invoice_number = invoice_response.json()['document_number']
    
    # Crea nota credito
    credit_response = client.post(
        "/api/v1/fiscal-documents/credit-notes",
        json={
            "id_invoice": invoice_id,
            "reason": "Reso",
            "is_partial": False,
            "is_electronic": True
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    credit_number = credit_response.json()['document_number']
    
    # Verifica numerazione separata
    assert invoice_number == '000001'
    assert credit_number == '000001'  # Note credito hanno numerazione propria


def test_numbering_reset_new_year(db_session, test_data):
    """
    Test reset numerazione all'inizio dell'anno
    
    NOTA: Questo test verifica la logica di numerazione.
    Il reset effettivo deve essere implementato con un job schedulato
    che resetta i contatori ogni 1 gennaio.
    """
    from src.repository.fiscal_document_repository import FiscalDocumentRepository
    
    repo = FiscalDocumentRepository(db_session)
    
    # Simula fatture dell'anno precedente
    old_invoice = FiscalDocument(
        document_type='invoice',
        tipo_documento_fe='TD01',
        id_order=test_data['order_it'].id_order,
        document_number='000099',
        is_electronic=True,
        status='sent',
        total_amount=1000.00,
        date_add=datetime(2024, 12, 31, 23, 59, 59)  # Anno precedente
    )
    db_session.add(old_invoice)
    db_session.commit()
    
    # Simula inizio nuovo anno
    new_invoice = FiscalDocument(
        document_type='invoice',
        tipo_documento_fe='TD01',
        id_order=test_data['order_it'].id_order,
        is_electronic=True,
        status='pending',
        total_amount=500.00,
        date_add=datetime(2025, 1, 1, 0, 0, 1)  # Nuovo anno
    )
    db_session.add(new_invoice)
    db_session.flush()
    
    # ATTUALMENTE: La numerazione continua (000100)
    # TODO: Implementare reset automatico il 1 gennaio
    next_number = repo._get_next_electronic_number('invoice')
    
    # Questo test documenta il comportamento attuale
    # Per reset automatico serve:
    # 1. Job schedulato (cron) che gira ogni 1 gennaio
    # 2. Filtra _get_next_electronic_number per anno corrente
    assert next_number == '000100'  # Continua (da implementare reset)
    
    # TODO: Dopo implementazione reset, dovrebbe essere:
    # assert next_number == '000001'  # Reset anno nuovo


def test_numbering_only_for_electronic(client, db_session, test_data, auth_token):
    """Test che solo fatture elettroniche hanno document_number sequenziale"""
    # Fattura elettronica
    response_electronic = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    # Fattura non elettronica
    response_non_electronic = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_fr'].id_order, "is_electronic": False},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response_electronic.json()['document_number'] == '000001'
    assert response_non_electronic.json()['document_number'] is None


# ==================== TEST RECUPERO DETTAGLI ====================

def test_get_invoice_details_with_products(client, db_session, test_data, auth_token):
    """Test recupero dettagli fattura con info prodotto"""
    # Crea fattura
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    
    # Recupera dettagli
    response = client.get(
        f"/api/v1/fiscal-documents/{invoice_id}/details-with-products",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 2
    
    # Verifica primo articolo
    assert data[0]['id_order_detail'] == test_data['order_detail_1'].id_order_detail
    assert data[0]['product_name'] == "Climatizzatore Daikin 12000 BTU"
    assert data[0]['product_reference'] == "DAIKIN-12K"
    assert data[0]['quantity'] == 3
    assert data[0]['unit_price'] == 155.033
    
    # Verifica secondo articolo
    assert data[1]['id_order_detail'] == test_data['order_detail_2'].id_order_detail
    assert data[1]['product_name'] == "Kit installazione"


def test_get_invoices_by_order(client, db_session, test_data, auth_token):
    """Test recupero tutte le fatture di un ordine"""
    # Crea 2 fatture
    client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": False},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    # Recupera tutte
    response = client.get(
        f"/api/v1/fiscal-documents/invoices/order/{test_data['order_it'].id_order}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_credit_notes_by_invoice(client, db_session, test_data, auth_token):
    """Test recupero note credito per fattura"""
    # Crea fattura
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    
    # Crea 2 note credito
    client.post(
        "/api/v1/fiscal-documents/credit-notes",
        json={
            "id_invoice": invoice_id,
            "reason": "Prima nota",
            "is_partial": False,
            "is_electronic": True
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    client.post(
        "/api/v1/fiscal-documents/credit-notes",
        json={
            "id_invoice": invoice_id,
            "reason": "Seconda nota",
            "is_partial": False,
            "is_electronic": True
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    # Recupera tutte
    response = client.get(
        f"/api/v1/fiscal-documents/credit-notes/invoice/{invoice_id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


# ==================== TEST VALIDAZIONI ====================

def test_create_invoice_order_not_found(client, db_session, test_data, auth_token):
    """Test errore ordine non trovato"""
    response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": 9999, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 400
    assert "non trovato" in response.json()['detail']


def test_create_credit_note_invoice_not_found(client, db_session, test_data, auth_token):
    """Test errore fattura non trovata"""
    response = client.post(
        "/api/v1/fiscal-documents/credit-notes",
        json={
            "id_invoice": 9999,
            "reason": "Test",
            "is_partial": False,
            "is_electronic": True
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 400
    assert "non trovata" in response.json()['detail']


def test_create_credit_note_electronic_for_non_electronic_invoice(client, db_session, test_data, auth_token):
    """Test errore nota elettronica per fattura non elettronica"""
    # Crea fattura non elettronica
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_fr'].id_order, "is_electronic": False},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    
    # Prova nota elettronica
    response = client.post(
        "/api/v1/fiscal-documents/credit-notes",
        json={
            "id_invoice": invoice_id,
            "reason": "Test",
            "is_partial": False,
            "is_electronic": True  # Errore
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 400
    assert "non elettronica" in response.json()['detail']


# ==================== TEST ELIMINAZIONE ====================

def test_delete_fiscal_document_pending(client, db_session, test_data, auth_token):
    """Test eliminazione documento con status pending"""
    # Crea fattura
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    
    # Elimina
    response = client.delete(
        f"/api/v1/fiscal-documents/{invoice_id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 204


def test_delete_fiscal_document_with_credit_notes_error(client, db_session, test_data, auth_token):
    """Test errore eliminazione fattura con note credito"""
    # Crea fattura
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    
    # Crea nota credito
    client.post(
        "/api/v1/fiscal-documents/credit-notes",
        json={
            "id_invoice": invoice_id,
            "reason": "Reso",
            "is_partial": False,
            "is_electronic": True
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    # Prova a eliminare fattura
    response = client.delete(
        f"/api/v1/fiscal-documents/{invoice_id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 400
    assert "note di credito collegate" in response.json()['detail']


# ==================== TEST FILTRI ====================

def test_get_fiscal_documents_filter_by_type(client, db_session, test_data, auth_token):
    """Test filtro per document_type"""
    # Crea fattura e nota
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    
    client.post(
        "/api/v1/fiscal-documents/credit-notes",
        json={
            "id_invoice": invoice_id,
            "reason": "Reso",
            "is_partial": False,
            "is_electronic": True
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    # Filtra solo fatture
    response = client.get(
        "/api/v1/fiscal-documents?document_type=invoice",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data['documents']) == 1
    assert data['documents'][0]['document_type'] == 'invoice'


def test_get_fiscal_documents_filter_by_electronic(client, db_session, test_data, auth_token):
    """Test filtro per is_electronic"""
    # Crea elettronica e non
    client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_fr'].id_order, "is_electronic": False},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    # Filtra solo elettroniche
    response = client.get(
        "/api/v1/fiscal-documents?is_electronic=true",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert all(doc['is_electronic'] for doc in data['documents'])


# ==================== TEST GENERAZIONE PDF ====================

def test_generate_invoice_pdf_success(client, db_session, test_data, auth_token):
    """Test generazione PDF per fattura completa"""
    # Crea fattura con dettagli
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    
    # Genera PDF
    response = client.get(
        f"/api/v1/fiscal-documents/{invoice_id}/pdf",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/pdf'
    assert 'attachment' in response.headers['content-disposition']
    assert 'fattura-000001.pdf' in response.headers['content-disposition']
    
    # Verifica che il contenuto sia un PDF valido
    content = response.content
    assert content.startswith(b'%PDF')  # Magic number PDF
    assert len(content) > 1000  # PDF ha dimensione ragionevole


def test_generate_credit_note_pdf_success(client, db_session, test_data, auth_token):
    """Test generazione PDF per nota di credito con riferimento fattura"""
    # Crea fattura
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    
    # Crea nota di credito
    credit_response = client.post(
        "/api/v1/fiscal-documents/credit-notes",
        json={
            "id_invoice": invoice_id,
            "reason": "Reso merce completo",
            "is_partial": False,
            "is_electronic": True
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    credit_id = credit_response.json()['id_fiscal_document']
    
    # Genera PDF
    response = client.get(
        f"/api/v1/fiscal-documents/{credit_id}/pdf",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/pdf'
    assert 'nota-credito-000001.pdf' in response.headers['content-disposition']
    
    # Verifica contenuto PDF
    content = response.content
    assert content.startswith(b'%PDF')
    assert len(content) > 1000


def test_generate_pdf_partial_credit_note(client, db_session, test_data, auth_token):
    """Test generazione PDF per nota di credito parziale"""
    # Crea fattura
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    
    # Crea nota di credito parziale
    credit_response = client.post(
        "/api/v1/fiscal-documents/credit-notes",
        json={
            "id_invoice": invoice_id,
            "reason": "Reso parziale - 1 articolo difettoso",
            "is_partial": True,
            "is_electronic": True,
            "items": [
                {
                    "id_order_detail": test_data['order_detail_1'].id_order_detail,
                    "quantity": 1,
                    "unit_price": 155.033
                }
            ]
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    credit_id = credit_response.json()['id_fiscal_document']
    
    # Genera PDF
    response = client.get(
        f"/api/v1/fiscal-documents/{credit_id}/pdf",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/pdf'


def test_generate_pdf_without_delivery_address(client, db_session, test_data, auth_token):
    """Test generazione PDF senza indirizzo consegna"""
    # Modifica order per rimuovere indirizzo consegna
    test_data['order_it'].id_address_delivery = None
    db_session.commit()
    
    # Crea fattura
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    
    # Genera PDF (non deve fallire)
    response = client.get(
        f"/api/v1/fiscal-documents/{invoice_id}/pdf",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/pdf'


def test_generate_pdf_document_not_found(client, db_session, test_data, auth_token):
    """Test errore 404 per documento non esistente"""
    response = client.get(
        "/api/v1/fiscal-documents/9999/pdf",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 404
    assert "non trovato" in response.json()['detail']


def test_generate_pdf_credit_note_without_reference_error(client, db_session, test_data, auth_token):
    """Test errore 400 per nota di credito senza riferimento fattura"""
    # Crea nota di credito manualmente senza riferimento (simulazione errore)
    # Nota: normalmente l'endpoint di creazione richiede id_invoice, 
    # ma testiamo il caso edge in cui sia presente solo nel DB
    from src.models.fiscal_document import FiscalDocument
    
    broken_credit_note = FiscalDocument(
        document_type='credit_note',
        id_order=test_data['order_it'].id_order,
        id_fiscal_document_ref=None,  # Senza riferimento
        status='pending',
        is_electronic=True
    )
    db_session.add(broken_credit_note)
    db_session.flush()
    
    # Aggiungi un dettaglio fittizio per superare il check "nessun dettaglio"
    from src.models.fiscal_document_detail import FiscalDocumentDetail
    detail = FiscalDocumentDetail(
        id_fiscal_document=broken_credit_note.id_fiscal_document,
        id_order_detail=test_data['order_detail_1'].id_order_detail,
        quantity=1,
        unit_price=100,
        total_amount=100
    )
    db_session.add(detail)
    db_session.commit()
    
    # Prova a generare PDF
    response = client.get(
        f"/api/v1/fiscal-documents/{broken_credit_note.id_fiscal_document}/pdf",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 400
    assert "senza riferimento" in response.json()['detail']


def test_generate_pdf_no_details_error(client, db_session, test_data, auth_token):
    """Test errore 404 per documento senza dettagli"""
    from src.models.fiscal_document import FiscalDocument
    
    # Crea documento senza dettagli
    empty_invoice = FiscalDocument(
        document_type='invoice',
        tipo_documento_fe='TD01',
        id_order=test_data['order_it'].id_order,
        document_number='999999',
        is_electronic=True,
        status='pending',
        total_amount=0
    )
    db_session.add(empty_invoice)
    db_session.commit()
    
    # Prova a generare PDF
    response = client.get(
        f"/api/v1/fiscal-documents/{empty_invoice.id_fiscal_document}/pdf",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 404
    assert "Nessun articolo trovato" in response.json()['detail']


def test_generate_pdf_with_discount(client, db_session, test_data, auth_token):
    """Test PDF con articoli scontati"""
    # Aggiungi sconto al order_detail
    test_data['order_detail_1'].reduction_percent = 10.0
    db_session.commit()
    
    # Crea fattura
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    
    # Genera PDF
    response = client.get(
        f"/api/v1/fiscal-documents/{invoice_id}/pdf",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/pdf'
    
    # Verifica che il PDF sia valido
    content = response.content
    assert content.startswith(b'%PDF')


def test_generate_pdf_with_payment_method(client, db_session, test_data, auth_token):
    """Test PDF con metodo di pagamento"""
    from src.models.payment import Payment
    
    # Crea metodo pagamento
    payment = Payment(id_payment=1, name="PayPal", is_complete_payment=True)
    db_session.add(payment)
    
    # Associa pagamento all'ordine
    test_data['order_it'].id_payment = 1
    db_session.commit()
    
    # Crea fattura
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    
    # Genera PDF
    response = client.get(
        f"/api/v1/fiscal-documents/{invoice_id}/pdf",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/pdf'


def test_generate_pdf_with_company_config(client, db_session, test_data, auth_token):
    """Test PDF con configurazioni aziendali"""
    from src.models.app_configuration import AppConfiguration
    
    # Aggiungi configurazioni aziendali
    configs = [
        AppConfiguration(category='company_info', name='company_name', value='ACME SRL'),
        AppConfiguration(category='company_info', name='company_vat', value='IT12345678901'),
        AppConfiguration(category='company_info', name='company_address', value='Via Roma 1'),
        AppConfiguration(category='company_info', name='company_city', value='Milano'),
        AppConfiguration(category='company_info', name='company_pec', value='acme@pec.it'),
        AppConfiguration(category='company_info', name='company_sdi', value='0000000'),
    ]
    db_session.add_all(configs)
    db_session.commit()
    
    # Crea fattura
    invoice_response = client.post(
        "/api/v1/fiscal-documents/invoices",
        json={"id_order": test_data['order_it'].id_order, "is_electronic": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    invoice_id = invoice_response.json()['id_fiscal_document']
    
    # Genera PDF
    response = client.get(
        f"/api/v1/fiscal-documents/{invoice_id}/pdf",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/pdf'
    
    # Il PDF dovrebbe contenere i dati aziendali
    # (Non possiamo verificare il contenuto del PDF facilmente, 
    # ma almeno verifichiamo che sia stato generato)
    content = response.content
    assert len(content) > 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
