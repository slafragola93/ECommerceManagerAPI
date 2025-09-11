from datetime import timedelta

from httpx import AsyncClient
from jose import jwt
from starlette import status

from src.routers.auth import authenticate_user, create_access_token, SECRET_KEY, ALHORITHM
from src.services.auth import get_current_user
from ..utils import *
from ..test_config import *  # Importa la configurazione di test per SECRET_KEY
import pytest
from fastapi import HTTPException

app.dependency_overrides[get_db] = override_get_db


@pytest.mark.anyio
async def test_login_success(test_user):
    async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/auth/") as ac:
        # Sostituisci queste credenziali con quelle valide per il test
        login_data = {
            "username": "elettronewtest",
            "password": "elettronew"
        }
        response = await ac.post("/login", data=login_data)

    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()
    assert "current_user" in response.json()
    assert response.json()["token_type"] == "bearer"

@pytest.mark.anyio
async def test_login_fail(test_user):
    async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/auth/") as ac:
        # Queste credenziali dovrebbero essere non valide
        login_data = {
            "username": "wrong_user",
            "password": "wrong_password"
        }
        response = await ac.post("/login", data=login_data)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# Testa il corretto funzionamento del login
def test_authenticate_user(test_user):
    """
        Testa il corretto funzionamento dell'autenticazione dell'utente.

        Verifica che:
        - Un utente esistente sia autenticato correttamente.
        - Un tentativo di autenticazione con un utente non esistente restituisca False.
        - Un tentativo di autenticazione con una password errata restituisca False.
    """
    db = TestingSessionLocal()
    authenticatd_user = authenticate_user(db, test_user.username, 'elettronew')
    assert authenticatd_user is not None
    assert authenticatd_user.username == test_user.username

    non_existent_user = authenticate_user(db, 'non_existent_user', 'testpassword')
    assert non_existent_user is False

    wrong_password_user = authenticate_user(db, test_user.username, 'wrongpassword')
    assert wrong_password_user is False


# Creazione del toke
def test_create_access_token():
    """
        Testa la creazione del token di accesso.

        Verifica che il token creato contenga i dati dell'utente corretti, incluso l'identificativo
        e il nome dell'utente.
    """
    user = "test_user"
    user_id = 1
    roles = Role(name="ADMIN", permissions="CRUD")
    token = create_access_token(username=user,
                                user_id=user_id,
                                expires_delta=timedelta(minutes=300),
                                roles=[roles])

    decoded_token = jwt.decode(token, SECRET_KEY,
                               algorithms=[ALHORITHM],
                               options={"verify_signature": False})

    assert decoded_token["sub"] == user
    assert decoded_token["id"] == user_id
    assert decoded_token["roles"] == [{"name": "ADMIN", "permissions": "CRUD"}]


# Testa se il token è valido
@pytest.mark.asyncio
async def test_get_current_user_valid_token():
    """
        Testa la validità del token fornito.

        Verifica che, dato un token valido, l'utente corrispondente venga correttamente identificato e restituito.
    """
    import os
    # Usa la stessa chiave che usa get_current_user
    test_secret_key = os.environ.get("SECRET_KEY", "test-secret-key")
    
    encode = {"sub": "test_user", "id": 1, "roles": [{"name": "ADMIN", "permissions": "CRUD"}]}  # , "roles": "Admin"}
    token = jwt.encode(encode, test_secret_key, algorithm=ALHORITHM)

    user = await get_current_user(token=token)  # Perchè è async si mette aewait
    assert user == {"username": "test_user", "id": 1, "roles": [{"name": "ADMIN", "permissions": "CRUD"}]}  # , "user_roles": "Admin"}


# test se non c e il payload
@pytest.mark.asyncio
async def test_get_current_user_invalid_token():
    """
        Testa il comportamento del sistema in presenza di un token non valido.

        Verifica che, dato un token non valido (senza il payload corretto), venga sollevata un'eccezione
        HTTP con status code 401, indicando che l'autenticazione non è riuscita.
    """
    encode = {"id": 1}
    token = jwt.encode(encode, SECRET_KEY, algorithm=ALHORITHM)

    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(token=token)

    assert excinfo.value.status_code == 401


def test_create_user_success(test_user):
    """
        Testa la creazione di un nuovo utente con successo.

        Verifica che, fornendo dati validi per un nuovo utente, questo venga correttamente creato
        nel database e che i dati salvati corrispondano a quelli forniti nella richiesta.
    """
    request_body = {
        "username": "oxRiL",
        "firstname": "test_name",
        "lastname": "last_name",
        "password": "password",
        "email": "user@example.com"
    }

    response = client.post("/api/v1/auth/register/", json=request_body)
    assert response.status_code == 201

    db = TestingSessionLocal()
    model = db.query(User).filter(User.id_user == 2).first()
    assert model.username == request_body.get('username')
    assert model.firstname == request_body.get('firstname')
    assert model.lastname == request_body.get('lastname')
    assert model.email == request_body.get('email')


def test_create_user_duplicate(test_user):
    """
        Testa il tentativo di creare un utente che esiste già.

        Verifica che, tentando di creare un utente già esistente, il sistema restituisca un errore
        con status code 400 e un messaggio che indica la presenza di un utente con dati duplicati.
    """
    request_body = {
        "username": "elettronewtest",
        "firstname": "test_name",
        "lastname": "last_name",
        "password": "password",
        "email": "user@example.com"
    }
    # Tentativo di creare lo stesso utente una seconda volta
    response = client.post("/api/v1/auth/register/", json=request_body)
    assert response.status_code == 400
    assert response.json()["detail"] == "Esiste già un utente con questi dati."
