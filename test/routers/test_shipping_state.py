from src import get_db
from src.main import app
from src.models import ShippingState
from src.services.auth import get_current_user
from ..utils import client, test_shipping_state, override_get_db, override_get_current_user, TestingSessionLocal, \
    override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


def test_get_all_shipping_state(test_shipping_state):
    """
    Testa la funzionalità di recupero di tutti gli stati di spedizione disponibili.
    Verifica che lo status code della risposta sia 200 e che i dati restituiti corrispondano
    a quelli previsti, inclusa la presenza dello stato di spedizione inserito per il test.
    """
    response = client.get("/api/v1/shipping_state/")

    # Verifica della risposta
    assert response.status_code == 200
    assert response.json() == [{
        'id_shipping_state': 1,
        'name': "Spedito",
    }]


def test_get_shipping_state_by_id(test_shipping_state):
    """
    Testa il recupero di uno specifico stato di spedizione tramite il suo ID.

    - Verifica che una richiesta per un ID inesistente restituisca uno status code 404, indicando che lo stato di spedizione non è stato trovato.
    - Verifica che una richiesta per un ID esistente restituisca i dati corretti dello stato di spedizione.
    """
    # Not found
    response = client.get("/api/v1/shipping_state/99")

    assert response.status_code == 404

    # Found
    response = client.get("/api/v1/shipping_state/1")
    assert response.json() == {
        'id_shipping_state': 1,
        'name': "Spedito",
    }


def test_create_shipping_state(test_shipping_state):
    """
    Testa la creazione di un nuovo stato di spedizione.

    Verifica che la richiesta POST con i dati del nuovo stato di spedizione restituisca uno status code 201
    e che lo stato di spedizione sia effettivamente creato nel database con i dati forniti.
    """
    request_body = {"name": "In Pronta Consegna"}
    response = client.post("/api/v1/shipping_state/", json=request_body)
    assert response.status_code == 201

    db = TestingSessionLocal()
    model = db.query(ShippingState).filter(ShippingState.id_shipping_state == 2).first()

    assert model.name == request_body.get('name')


def test_update_shipping_state(test_shipping_state):
    """
    Testa l'aggiornamento dei dati di uno stato di spedizione esistente.

    Verifica che una richiesta PUT con i nuovi dati dello stato di spedizione restituisca uno status code 204,
    e che i dati dello stato di spedizione nel database siano aggiornati correttamente con i nuovi valori forniti.
    """
    request_body = {"name": "In consegna"}
    response = client.put("/api/v1/shipping_state/1", json=request_body)
    assert response.status_code == 204

    db = TestingSessionLocal()
    model = db.query(ShippingState).filter(ShippingState.id_shipping_state == 1).first()

    assert model.name == request_body.get('name')


# TEST CON PERMESSI USER

def test_get_all_shipping_state_with_user_permissions(test_shipping_state):
    app.dependency_overrides[get_current_user] = override_get_current_user_read_only
    response = client.get("/api/v1/shipping_state/")

    # Verifica della risposta
    assert response.status_code == 403


def test_get_shipping_state_by_id_with_user_permissions(test_shipping_state):
    response = client.get("/api/v1/shipping_state/99")

    assert response.status_code == 403


def test_create_shipping_state_with_user_permissions(test_shipping_state):
    request_body = {"name": "In Pronta Consegna"}
    response = client.post("/api/v1/shipping_state/", json=request_body)
    assert response.status_code == 403


def test_update_shipping_state_with_user_permissions(test_shipping_state):
    request_body = {"name": "In consegna"}
    response = client.put("/api/v1/shipping_state/1", json=request_body)
    assert response.status_code == 403
    app.dependency_overrides[get_current_user] = override_get_current_user