from fastapi import APIRouter, Depends, status, HTTPException
from dotenv import load_dotenv
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from typing import Annotated
from datetime import datetime, timedelta
import os

from src.models.role import PermissionType
from src.schemas.user_schema import *
from src.services.routers.auth_service import *
from src.core.dependencies import db_dependency
from src.core.exceptions import (
    ValidationException,
    AuthenticationException
)

load_dotenv()

router = APIRouter(
    prefix='/api/v1/auth',
    tags=['Authentication'],
)

SECRET_KEY = os.environ.get("SECRET_KEY")


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def create_user(db: db_dependency, us: UserSchema):
    """Crea un nuovo utente nel sistema."""
    from src.models.user import User
    from src import Role

    user = User(
        username  = us.username,
        email     = us.email,
        firstname = us.firstname,
        lastname  = us.lastname,
        password  = bcrypt_context.hash(us.password)
    )

    if us.roles:
        role_ids = [role.id_role for role in us.roles]
        roles = db.query(Role).filter(Role.id_role.in_(role_ids)).all()
        user.roles = roles
    else:
        default_role = db.query(Role).filter(Role.name == "USER").first()
        if not default_role:
            raise ValidationException("Default role 'USER' not found")
        user.roles.append(default_role)

    db.add(user)
    db.commit()
    return user


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def get_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: db_dependency
):
    """Autentica un utente e restituisce access token + refresh token."""

    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise AuthenticationException("Credenziali non valide")

    # Prende il ruolo principale dell'utente
    role = user.roles[0] if user.roles else None
    role_name = role.name if role else "USER"
    role_type = role.permission_type.value if role else PermissionType.custom.value

    # Access token — 30 minuti
    access_token = create_access_token(
        username  = user.username,
        user_id   = user.id_user,
        role_name = role_name,
        role_type = role_type,
        expires_delta = timedelta(minutes=30)
    )

    # Refresh token — 7 giorni, salvato nel DB
    refresh_token = create_refresh_token(
        user_id     = user.id_user,
        db          = db,
        device_info = None,
        ip_address  = None
    )

    expires_at = datetime.now() + timedelta(minutes=30)

    return {
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "token_type":    "bearer",
        "current_user":  form_data.username,
        "expires_at":    expires_at
    }


@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh_token(
    payload: dict,
    db: db_dependency
):
    """
    Rinnova l'access token usando il refresh token.
    Il client manda: { "refresh_token": "..." }
    """
    raw_token = payload.get("refresh_token")
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token mancante"
        )

    # Verifica il refresh token nel DB
    refresh = verify_refresh_token(raw_token, db)

    # Carica l'utente
    from src.models.user import User
    user = db.query(User).filter(
        User.id_user == refresh.id_user
    ).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utente non trovato o disattivato"
        )

    role = user.roles[0] if user.roles else None
    role_name = role.name if role else "USER"
    role_type = role.permission_type.value if role else PermissionType.custom.value

    # Nuovo access token
    new_access_token = create_access_token(
        username      = user.username,
        user_id       = user.id_user,
        role_name     = role_name,
        role_type     = role_type,
        expires_delta = timedelta(minutes=30)
    )

    expires_at = datetime.now() + timedelta(minutes=30)

    return {
        "access_token": new_access_token,
        "token_type":   "bearer",
        "expires_at":   expires_at
    }


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    payload: dict,
    db: db_dependency
):
    """
    Revoca il refresh token — invalida la sessione.
    Il client manda: { "refresh_token": "..." }
    """
    raw_token = payload.get("refresh_token")
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token mancante"
        )

    revoke_refresh_token(raw_token, db)

    return {"message": "Logout effettuato con successo"}

@router.post("/logout-all", status_code=status.HTTP_200_OK)
async def logout_all(
    db: db_dependency,
    user: dict = Depends(get_current_user)
):
    """
    Revoca TUTTI i refresh token dell'utente loggato.
    Usato per "logout da tutti i dispositivi" o quando si sospetta
    una compromissione dell'account.

    Richiede autenticazione (Bearer token valido).
    """
    user_id = user["id"]
    count = revoke_all_user_tokens(user_id, db)
    return {"message": f"Logout effettuato da tutti i dispositivi", "tokens_revoked": count}