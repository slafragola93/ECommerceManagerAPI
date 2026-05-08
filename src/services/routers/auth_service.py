import os
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Annotated, Optional
from functools import wraps

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from starlette import status

from src.database import get_db
from src.models.user import User
from src.models.refresh_token import RefreshToken

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

db_dependency = Annotated[Session, Depends(get_db)]
token_dependency = Annotated[str, Depends(oauth2_bearer)]


# ──────────────────────────────────────────────────────────
# AUTENTICAZIONE BASE
# ──────────────────────────────────────────────────────────

def authenticate_user(db: Session, username: str, password: str):
    """Verifica username e password. Restituisce User o False."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not bcrypt_context.verify(password, user.password):
        return False
    return user


# ──────────────────────────────────────────────────────────
# ACCESS TOKEN
# ──────────────────────────────────────────────────────────

def create_access_token(
    username: str,
    user_id: int,
    role_name: str,
    role_type: str,
    expires_delta: timedelta = timedelta(minutes=30)
) -> str:
    """
    Genera un JWT snello con solo identità e tipo ruolo.
    Scadenza default: 30 minuti.
    """
    payload = {
        "sub":       username,
        "id":        user_id,
        "role":      role_name,
        "role_type": role_type,
        "exp":       datetime.now() + expires_delta
    }
    return jwt.encode(
        payload,
        os.environ.get("SECRET_KEY"),
        algorithm="HS256"
    )


async def get_current_user(token: token_dependency) -> dict:
    """
    Dependency FastAPI: decodifica il JWT e restituisce i dati utente.
    """
    try:
        payload = jwt.decode(
            token,
            os.environ.get("SECRET_KEY"),
            algorithms=["HS256"]
        )
        username:  str = payload.get("sub")
        user_id:   int = payload.get("id")
        role:      str = payload.get("role")
        role_type: str = payload.get("role_type")

        if username is None or user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenziali non valide"
            )

        return {
            "username":  username,
            "id":        user_id,
            "role":      role,
            "role_type": role_type
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o scaduto"
        )


# ──────────────────────────────────────────────────────────
# REFRESH TOKEN
# ──────────────────────────────────────────────────────────

def create_refresh_token(
    user_id: int,
    db: Session,
    device_info: Optional[str] = None,
    ip_address: Optional[str] = None,
    expires_days: int = 7
) -> str:
    """
    Genera un refresh token opaco.
    Salva SHA-256 nel DB, restituisce il token in chiaro al client.
    """
    raw_token  = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    refresh = RefreshToken(
        id_user     = user_id,
        token_hash  = token_hash,
        device_info = device_info,
        ip_address  = ip_address,
        expires_at  = datetime.now() + timedelta(days=expires_days),
        created_at  = datetime.now()
    )
    db.add(refresh)
    db.commit()

    return raw_token


def verify_refresh_token(raw_token: str, db: Session) -> RefreshToken:
    """
    Verifica un refresh token ricevuto dal client.
    Lancia 401 se non trovato, scaduto o revocato.
    """
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    refresh = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash
    ).first()

    if not refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token non valido"
        )

    if not refresh.is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token scaduto o revocato"
        )

    return refresh


def revoke_refresh_token(raw_token: str, db: Session) -> bool:
    """
    Revoca un refresh token — usato dal logout.
    """
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    refresh = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash
    ).first()

    if not refresh:
        return False

    refresh.revoke()
    db.commit()
    return True


def revoke_all_user_tokens(user_id: int, db: Session) -> int:
    """
    Revoca TUTTI i refresh token attivi di un utente.
    Usato per "logout da tutti i dispositivi" o quando si rileva
    una compromissione dell'account.

    Restituisce il numero di token revocati.
    """
    now = datetime.now()

    # Cerca tutti i refresh token attivi (non scaduti, non revocati)
    active_tokens = db.query(RefreshToken).filter(
        RefreshToken.id_user == user_id,
        RefreshToken.revoked_at.is_(None),
        RefreshToken.expires_at > now
    ).all()

    count = 0
    for token in active_tokens:
        token.revoke()
        count += 1

    if count > 0:
        db.commit()

    return count

# ──────────────────────────────────────────────────────────
# REQUIRE PERMISSION — nuovo sistema granulare
# ──────────────────────────────────────────────────────────

def require_permission(module: str, action: str):
    """
    FastAPI Depends per proteggere gli endpoint con permessi granulari.

    Uso:
    @router.get("/orders")
    async def get_orders(
        _=Depends(require_permission("orders", "read")),
        user=Depends(get_current_user)
    ):
    """
    async def check(
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        from src.models.role import PermissionType
        from src.models.app_modules import AppModule
        from src.models.user_module_permission import UserModulePermission
        from sqlalchemy import and_

        user_id   = current_user["id"]
        role_type = current_user.get("role_type")

        # ADMIN → accesso totale
        if role_type == PermissionType.full_crud.value:
            return current_user

        # Carica il modulo
        app_module = db.query(AppModule).filter(
            AppModule.name == module,
            AppModule.is_active == True
        ).first()

        if not app_module:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Modulo '{module}' non trovato"
            )

        # Cerca override personale
        perm = db.query(UserModulePermission).filter(
            and_(
                UserModulePermission.id_user == user_id,
                UserModulePermission.id_module == app_module.id_module,
                UserModulePermission.id_role.is_(None)
            )
        ).first()

        # Se non c'è override cerca permesso del ruolo
        if not perm:
            user = db.query(User).filter(User.id_user == user_id).first()
            if user and user.roles:
                role_id = user.roles[0].id_role
                perm = db.query(UserModulePermission).filter(
                    and_(
                        UserModulePermission.id_role == role_id,
                        UserModulePermission.id_module == app_module.id_module,
                        UserModulePermission.id_user.is_(None)
                    )
                ).first()

        if not perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permesso mancante: {module}.{action}"
            )

        action_map = {
            'read':   perm.can_read,
            'create': perm.can_create,
            'update': perm.can_update,
            'delete': perm.can_delete,
        }

        if not action_map.get(action, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permesso mancante: {module}.{action}"
            )

        return current_user

    return check


# ──────────────────────────────────────────────────────────
# CHECK PERMISSION — versione manuale (non-Depends) di require_permission
# ──────────────────────────────────────────────────────────

def check_permission(
    user_dict: dict,
    db: Session,
    module: str,
    action: str
) -> None:
    """
    Verifica manuale di un permesso, chiamabile dal body di un endpoint.

    Versione "non-Depends" di `require_permission`: stessa identica logica e
    stesse exception, ma invocabile imperativamente quando il check è
    condizionale (es. self-read di un profilo utente).

    Solleva HTTPException 403 se il permesso manca.
    Bypass per role_type=full_crud (coerente con `require_permission`).

    Uso tipico:
        check_permission(user, db, "users", "read")
    """
    from src.models.role import PermissionType
    from src.models.app_modules import AppModule
    from src.models.user_module_permission import UserModulePermission
    from sqlalchemy import and_

    user_id   = user_dict["id"]
    role_type = user_dict.get("role_type")

    if role_type == PermissionType.full_crud.value:
        return

    app_module = db.query(AppModule).filter(
        AppModule.name == module,
        AppModule.is_active == True
    ).first()

    if not app_module:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Modulo '{module}' non trovato"
        )

    perm = db.query(UserModulePermission).filter(
        and_(
            UserModulePermission.id_user == user_id,
            UserModulePermission.id_module == app_module.id_module,
            UserModulePermission.id_role.is_(None)
        )
    ).first()

    if not perm:
        user_obj = db.query(User).filter(User.id_user == user_id).first()
        if user_obj and user_obj.roles:
            role_id = user_obj.roles[0].id_role
            perm = db.query(UserModulePermission).filter(
                and_(
                    UserModulePermission.id_role == role_id,
                    UserModulePermission.id_module == app_module.id_module,
                    UserModulePermission.id_user.is_(None)
                )
            ).first()

    if not perm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permesso mancante: {module}.{action}"
        )

    action_map = {
        'read':   perm.can_read,
        'create': perm.can_create,
        'update': perm.can_update,
        'delete': perm.can_delete,
    }

    if not action_map.get(action, False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permesso mancante: {module}.{action}"
        )


# ──────────────────────────────────────────────────────────
# AUTHORIZE — mantenuto per retrocompatibilità
# ──────────────────────────────────────────────────────────

def authorize(roles_permitted: list, permissions_required: list):
    """
    Decorator mantenuto per retrocompatibilità con i router esistenti.
    Aggiornato per supportare il nuovo formato JWT (role come stringa).
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get("user")

            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="Utente non autenticato"
                )

            # Supporta sia vecchio formato (roles lista)
            # che nuovo formato (role stringa)
            if 'role' in user:
                user_roles = [user['role']]
            elif 'roles' in user:
                user_roles = [r["name"] for r in user.get('roles', [])]
            else:
                raise HTTPException(
                    status_code=401,
                    detail="Ruoli utente non trovati"
                )

            roles_check = any(
                role in roles_permitted for role in user_roles
            )
            if not roles_check:
                raise HTTPException(
                    status_code=403,
                    detail="Utente non autorizzato"
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


# ──────────────────────────────────────────────────────────
# RESET PASSWORD
# ──────────────────────────────────────────────────────────

def create_reset_password_token(email: str) -> str:
    """Crea un token per il reset della password"""
    data = {
        "sub": email,
        "exp": datetime.now() + timedelta(minutes=10)
    }
    return jwt.encode(
        data,
        os.environ.get("FORGET_PWD_SECRET_KEY"),
        algorithm="HS256"
    )