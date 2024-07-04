from sqlalchemy import text

from src import get_db, User
from src.main import app
from src.services.auth import get_current_user
from ..utils import client, test_users, override_get_db, override_get_current_user, TestingSessionLocal

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


def test_get_all_users(test_users):
    response = client.get("/api/v1/users/")

    # Verifica della risposta
    assert response.status_code == 200


def test_get_user_by_id(test_users):
    response = client.get("/api/v1/users/10")

    # Verifica della risposta
    assert response.status_code == 404

    response = client.get("/api/v1/users/2")
    # Verifica della risposta
    assert response.json()["firstname"] == "Enzo"
    assert response.json()["lastname"] == "Mastrict"
    assert response.status_code == 200


def test_update_user(test_users):
    request_body = {
        "lastname": "Ancelotti",
        "email": "carloancelotti@mail.com",
        "username": "cancelotti",
        "firstname": "Carlo",
        "password": "testpassword"
    }

    response = client.put("/api/v1/users/1", json=request_body)
    assert response.status_code == 204

    db = TestingSessionLocal()

    user = db.query(User).filter(User.id_user == 1).first()
    assert user is not None

    assert user.firstname == request_body.get('firstname')
    assert user.email == request_body.get('email')
    assert user.username == request_body.get('username')


def test_delete_user(test_users):
    response = client.delete("/api/v1/users/1")
    assert response.status_code == 204

    db = TestingSessionLocal()

    user_in_db = db.query(User).filter(User.username == "salvioc").first()
    assert user_in_db is None

    # Verifica che il record nella tabella user_roles sia stato cancellato
    user_role_in_db = db.execute(text("SELECT * FROM user_roles WHERE id_user = :user_id"), {'user_id': 1}).fetchone()
    assert user_role_in_db is None


