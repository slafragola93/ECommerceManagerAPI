from src import get_db, OrderState
from src.main import app
from src.models import OrderState
from src.services.auth import get_current_user
from ..utils import client, test_order_state, override_get_db, override_get_current_user, TestingSessionLocal, \
    override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


def test_get_all_order_state(test_order_state):
    response = client.get("/api/v1/order_state/")

    # Verifica della risposta
    assert response.status_code == 200
    assert response.json() == [
        {
            'id_order_state': 1,
            'name': "In attesa di conferma",
        },
        {
            'id_order_state': 2,
            'name': "In corso",
        },
        {
            'id_order_state': 3,
            'name': "Confermata",
        },
        {
            'id_order_state': 4,
            'name': "Annullata",
        }
    ]


def test_get_order_state_by_id(test_order_state):
    # Not found
    response = client.get("/api/v1/order_state/99")

    assert response.status_code == 404

    # Found
    response = client.get("/api/v1/order_state/1")
    assert response.json() == {
        'id_order_state': 1,
        'name': "In attesa di conferma",
    }


def test_create_order_state(test_order_state):

    request_body = {"name": "Test creazione ordine"}
    response = client.post("/api/v1/order_state/", json=request_body)
    assert response.status_code == 201

    db = TestingSessionLocal()
    model = db.query(OrderState).filter(OrderState.id_order_state == 5).first()

    assert model.name == request_body.get('name')


def test_update_order_state(test_order_state):
    request_body = {"name": "Test modifica ordine"}
    response = client.put("/api/v1/order_state/1", json=request_body)
    assert response.status_code == 204

    db = TestingSessionLocal()
    model = db.query(OrderState).filter(OrderState.id_order_state == 1).first()

    assert model.name == request_body.get('name')
