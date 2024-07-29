import os
from datetime import datetime, timedelta
from typing import Annotated
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from starlette import status
from functools import wraps
from fastapi import HTTPException

from src import Role
from src.database import get_db
from src.models.user import User

# Questo service si occupa di fornire tutte le dipendenza ad auth.py

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

db_dependency = Annotated[Session, Depends(get_db)]
token_dependency = Annotated[str, Depends(oauth2_bearer)]


def authenticate_user(db: db_dependency, username: str, password: str):
    """Authentication utente."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not bcrypt_context.verify(password, user.password):
        return False
    return user


async def get_current_user(token: token_dependency):
    """Valida token in ogni endpoint della applicazione."""
    try:
        payload = jwt.decode(token, os.environ.get("SECRET_KEY"), algorithms=["HS256"])
        username: str = payload.get("sub")
        user_id: int = payload.get("id")
        roles: list = payload.get("roles")
        # TODO: ottieni anche ruolo + permessi

        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenziali non valide")
        # TODO: aggiungere il controllo sul ruolo + permessi
        return {"username": username, "id": user_id, "roles": roles}
    except JWTError:
        print(token)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token non valido o scaduto")


def create_access_token(username: str, user_id: int, roles: list[Role], expires_delta: timedelta):
    """Genera il token di accesso"""
    # TODO: aggiungerel ruolo + permessi
    encode = {"sub": username, "id": user_id,
              "roles": [{"name": role.name, "permissions": role.permissions} for role in roles]}

    if expires_delta:
        expires = datetime.utcnow() + expires_delta
    else:
        expires = datetime.utcnow() + timedelta(days=365)

    encode.update({"exp": expires})

    return jwt.encode(encode, os.environ.get("SECRET_KEY"), algorithm="HS256")


def create_reset_password_token(email: str):
    """Crea un token per il reset della password"""
    data = {"sub": email, "exp": datetime.utcnow() + timedelta(minutes=10)}
    token = jwt.encode(data, os.environ.get("FORGET_PWD_SECRET_KEY"), "HS256")
    return token


def check_user_permissions(user: dict = Depends(get_current_user)):
    user_id = user.get("user_id")
    # Qui va la logica per controllare i permessi dell'utente
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="L'utente non ha i permessi necessari",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def authorize(roles_permitted: list, permissions_required: list):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get("user")
            user_roles = [user_role["name"] for user_role in user['roles']]
            user_permissions = set()

            # Estrai i permessi dai ruoli dell'utente
            for role in user['roles']:
                user_permissions.update(role['permissions'])  # Supponendo che ogni ruolo abbia una lista di permessi

            # Verifica i ruoli permessi
            if not any(role in roles_permitted for role in user_roles):
                raise HTTPException(status_code=403, detail="Utente non autorizzato.")

            # Verifica i permessi richiesti
            if not all(permission in user_permissions for permission in permissions_required):
                raise HTTPException(status_code=403, detail="Permessi insufficienti.")

            return await func(*args, **kwargs)

        return wrapper

    return decorator
