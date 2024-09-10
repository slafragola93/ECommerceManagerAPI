from datetime import datetime, date

from src import get_db
from src.main import app
from src.models import Address
from src.services.auth import get_current_user
from ..utils import client, test_address, test_addresses, test_customer, override_get_db, override_get_current_user, \
    TestingSessionLocal, override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

expected_address = [
    {
        'id_address': 2,
        'id_origin': 150,
        'customer':
            {
                'id_customer': 1,
                'id_origin': 0,
                'id_lang': 1,
                'firstname': 'Enzo',
                'lastname': 'Cristiano',
                'email': 'enzocristiano@elettronew.com',
                'date_add': date.today().strftime('%Y-%m-%dT00:00:00')
            },
        'country':
            {
                'id_country': 2,
                'name': 'Italia',
                'iso_code': 'IT'
            },
        'company': 'Elettronew FR',
        'firstname': 'Enzo',
        'lastname': 'Cristiano',
        'address1': 'Rue Sainte 10',
        'address2': '',
        'state': 'Bouche du rhone',
        'postcode': '13007',
        'city': 'Marseille',
        'phone': '34567890',
        'mobile_phone': '34567890',
        'vat': '02469660209',
        'dni': 'dni',
        'pec': 'enzocristiano@pec.it',
        'sdi': 'sdi',
        'date_add': date.today().strftime('%d-%m-%Y')
    },
    {
        "id_address": 1,
        "id_origin": 0,
        "customer": {
            "id_customer": 1,
            "id_origin": 0,
            "id_lang": 1,
            "firstname": "Enzo",
            "lastname": "Cristiano",
            "email": "enzocristiano@elettronew.com",
            "date_add": datetime.today().strftime('%Y-%m-%dT00:00:00')
        },
        "country": {
            "id_country": 1,
            "name": "Italia",
            "iso_code": "IT"
        },
        "company": "Elettronew",
        "firstname": "Enzo",
        "lastname": "Cristiano",
        "address1": "Via Roma",
        "address2": "Casa",
        "state": "Campania",
        "postcode": "80010",
        "city": "Napoli",
        "phone": "34567890",
        "mobile_phone": "34567890",
        "vat": "02469660209",
        "dni": "dni",
        "pec": "enzocristiano@pec.it",
        "sdi": "sdi",
        "date_add": datetime.today().strftime('%d-%m-%Y')
    }
]


def test_get_all_addresses(test_customer, test_address):
    """
      Testa la funzionalità di recupero di tutti gli indirizzi
      Verifica che la risposta includa l'indirizzo corretto associato al cliente di test.
      """
    response = client.get("/api/v1/addresses/")
    # Verifica della risposta
    assert response.status_code == 200
    assert response.json()["addresses"] == [expected_address[1]]


def test_get_addresses_by_filters(test_customer, test_addresses):
    """
    Testa il recupero degli indirizzi applicando specifici filtri.
    Controlla che solo gli indirizzi corrispondenti ai criteri di filtro siano restituiti.
    """
    response = client.get("/api/v1/addresses/?addresses_ids=10")

    # Verifica della risposta
    assert response.status_code == 404

    response = client.get("/api/v1/addresses/?addresses_ids=1,2&customers=1")

    # Verifica della risposta
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["addresses"][1] == expected_address[1]
    assert response.json()["addresses"][0] == expected_address[0]

    response = client.get("/api/v1/addresses/?countries=3&customers=1")
    assert response.status_code == 404


def test_get_address_by_id(test_customer, test_addresses):
    """
    Testa la funzionalità di recupero di un indirizzo specifico tramite il suo ID.
    Assicura che l'indirizzo restituito sia quello corretto associato all'ID fornito.
    """
    response = client.get('/api/v1/addresses/2')

    # Verifica della risposta
    assert response.status_code == 200

    assert response.json() == expected_address[0]

    response = client.get('/api/v1/addresses/3')
    assert response.status_code == 404


def test_create_address(test_customer, test_address):
    """
     Testa la capacità di creare un nuovo indirizzo per un cliente.
     Verifica che l'indirizzo creato sia aggiunto correttamente al database e che i suoi dati corrispondano a quelli forniti.
     """
    request_body = {
        "id_origin": 0,
        "id_country": 1,
        "customer": {
            'id_origin': 0,
            'id_lang': 1,
            'firstname': 'Luca',
            'lastname': 'Sponzi',
            'email': 'lucasponzi@elettronew.com',
            'date_add': date.today().strftime('%Y-%m-%dT00:00:00')
        },
        "company": "MegaWatt",
        "firstname": "Gianni",
        "lastname": "Marigliano",
        "address1": "Circumvallazione esterna 89",
        "address2": "",
        "state": "Casoria",
        "postcode": "80026",
        "city": "Napoli",
        "phone": "0813614614",
        "mobile_phone": "",
        "vat": "05907491210",
        "dni": "",
        "pec": "",
        "sdi": ""
    }

    response = client.post("/api/v1/addresses/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 201

    db = TestingSessionLocal()

    address = db.query(Address).filter(Address.id_address == 2).first()
    assert address is not None

    assert address.id_origin == request_body.get('id_origin')
    assert address.id_country == request_body.get('id_country')
    assert address.id_customer == 2
    assert address.firstname == request_body.get('firstname')
    assert address.address1 == request_body.get('address1')
    assert address.city == request_body.get('city')

    request_body = request_body.pop('firstname', None)

    response = client.post("/api/v1/addresses/", json=request_body)
    assert response.status_code == 422

    # request_body = {
    #     "id_origin": 0,
    #     "id_country": 1,
    #     "customer": 1,
    #     "company": "MegaWatt",
    #     "firstname": "Gianni",
    #     "lastname": "Marigliano",
    #     "address1": "Circumvallazione esterna 89",
    #     "address2": "",
    #     "state": "Casoria",
    #     "postcode": "80026",
    #     "city": "Napoli",
    #     "phone": "0813614614",
    #     "mobile_phone": "",
    #     "vat": "05907491210",
    #     "dni": "",
    #     "pec": "",
    #     "sdi": ""
    # }
    # response = client.post("/api/v1/addresses/", json=request_body)
    #
    # # Verifica della risposta
    # assert response.status_code == 201
    #
    # db = TestingSessionLocal()
    #
    # address = db.query(Address).filter(Address.id_address == 3).first()
    # assert address is not None
    #
    # assert address.id_origin == request_body.get('id_origin')
    # assert address.id_country == request_body.get('id_country')
    # assert address.id_customer == request_body.get('id_customer')
    # assert address.firstname == request_body.get('firstname')
    # assert address.address1 == request_body.get('address1')
    # assert address.city == request_body.get('city')


def test_delete_address(test_customer, test_addresses):
    """
    Testa la funzionalità di eliminazione di un indirizzo.
    Verifica che l'indirizzo specificato sia rimosso dal database e non sia più recuperabile.
    """
    # not found
    response = client.delete('/api/v1/addresses/200')
    assert response.status_code == 404

    response = client.delete("/api/v1/addresses/2")

    # Verifica della risposta
    assert response.status_code == 204


def test_update_address(test_customer, test_address):
    """
      Testa la capacità di aggiornare i dettagli di un indirizzo esistente.
      Controlla che l'indirizzo aggiornato nel database rifletta le modifiche apportate.
      """
    request_body = {
        "id_origin": 0,
        "id_country": 1,
        "id_customer": 1,
        "company": "Emmebistore",
        "firstname": "Gianni",
        "lastname": "Marigliano",
        "address1": "Circumvallazione esterna 89",
        "address2": "",
        "state": "Casoria",
        "postcode": "80026",
        "city": "Napoli",
        "phone": "0813614614",
        "mobile_phone": "",
        "vat": "05907491210",
        "dni": "",
        "pec": "",
        "sdi": ""
    }

    response = client.put("/api/v1/addresses/1", json=request_body)
    assert response.status_code == 200

    db = TestingSessionLocal()

    address = db.query(Address).filter(Address.id_address == 1).first()
    assert address is not None

    assert address.firstname == request_body.get('firstname')
    assert address.company == request_body.get('company')
    assert address.id_address == 1


### TEST SENZA PERMESSI
def test_update_endpoint_with_user_permissions(test_customer, test_address):
    app.dependency_overrides[get_current_user] = override_get_current_user_read_only
    request_body = {
        "id_origin": 0,
        "id_country": 1,
        "id_customer": 1,
        "company": "Emmebistore",
        "firstname": "Gianni",
        "lastname": "Marigliano",
        "address1": "Circumvallazione esterna 89",
        "address2": "",
        "state": "Casoria",
        "postcode": "80026",
        "city": "Napoli",
        "phone": "0813614614",
        "mobile_phone": "",
        "vat": "05907491210",
        "dni": "",
        "pec": "",
        "sdi": ""
    }

    response = client.put("/api/v1/addresses/1", json=request_body)
    assert response.status_code == 403


def test_create_address_with_user_permissions(test_customer, test_address):
    """
     Testa la capacità di creare un nuovo indirizzo per un cliente.
     Verifica che l'indirizzo creato sia aggiunto correttamente al database e che i suoi dati corrispondano a quelli forniti.
     """
    request_body = {
        "id_origin": 0,
        "id_country": 1,
        "id_customer": 1,
        "company": "MegaWatt",
        "firstname": "Gianni",
        "lastname": "Marigliano",
        "address1": "Circumvallazione esterna 89",
        "address2": "",
        "state": "Casoria",
        "postcode": "80026",
        "city": "Napoli",
        "phone": "0813614614",
        "mobile_phone": "",
        "vat": "05907491210",
        "dni": "",
        "pec": "",
        "sdi": ""
    }

    response = client.post("/api/v1/addresses/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 403


def test_delete_address_with_user_permissions(test_customer, test_addresses):
    """
    Testa la funzionalità di eliminazione di un indirizzo.
    Verifica che l'indirizzo specificato sia rimosso dal database e non sia più recuperabile.
    """
    # not found
    response = client.delete('/api/v1/addresses/200')
    assert response.status_code == 403

    app.dependency_overrides[get_current_user] = override_get_current_user
