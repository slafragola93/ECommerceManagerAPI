import os
import secrets
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional
from functools import wraps

import pyotp
from cryptography.fernet import Fernet
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
# PERMISSION DENIED — helper per body strutturato 403
# ──────────────────────────────────────────────────────────

PermissionDeniedReason = Literal["module_not_found", "permission_missing", "permission_zero"]


def _raise_permission_denied(
    module: str,
    action: str,
    reason: PermissionDeniedReason,
) -> None:
    """
    Solleva HTTPException 403 con body strutturato per errori di permission RBAC.

    Il body resta machine-readable per il frontend:
    {
        "error_code": "PERMISSION_DENIED",
        "message": "Non hai i permessi necessari per questa operazione.",
        "module": "settings",
        "action": "update",
        "reason": "permission_missing"
    }
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error_code": "PERMISSION_DENIED",
            "message": "Non hai i permessi necessari per questa operazione.",
            "module": module,
            "action": action,
            "reason": reason,
        },
    )


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
    Popola anche il ContextVar attore per l'audit trail (EventBus metadata).
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

        try:
            from src.core.request_context import set_actor

            set_actor(
                actor_id=user_id,
                username=username or "system",
                role=role or "",
            )
        except Exception:
            pass

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
# REQUIRE ADMIN — per endpoint infrastrutturali senza modulo di business
# (cache, metrics): non passano dal sistema granulare a moduli perché non
# appartengono a nessun modulo, quindi si verifica solo il ruolo ADMIN.
# ──────────────────────────────────────────────────────────

def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """FastAPI Depends: consente l'accesso solo a utenti con ruolo ADMIN."""
    from src.models.role import PermissionType

    if current_user.get("role_type") != PermissionType.full_crud.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Riservato agli amministratori",
        )
    return current_user


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
            _raise_permission_denied(module, action, "module_not_found")

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
            _raise_permission_denied(module, action, "permission_missing")

        action_map = {
            'read':   perm.can_read,
            'create': perm.can_create,
            'update': perm.can_update,
            'delete': perm.can_delete,
        }

        if not action_map.get(action, False):
            _raise_permission_denied(module, action, "permission_zero")

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
        _raise_permission_denied(module, action, "module_not_found")

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
        _raise_permission_denied(module, action, "permission_missing")

    action_map = {
        'read':   perm.can_read,
        'create': perm.can_create,
        'update': perm.can_update,
        'delete': perm.can_delete,
    }

    if not action_map.get(action, False):
        _raise_permission_denied(module, action, "permission_zero")


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
# MFA / 2FA
# ──────────────────────────────────────────────────────────

MFA_TTL_MINUTES = 5
MFA_MAX_ATTEMPTS = 5
MFA_RESEND_COOLDOWN_SECONDS = 60
MFA_OTP_LENGTH = 6
TOTP_ISSUER = "Elettronew"


def _hash_opaque_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _fernet() -> Fernet:
    secret = (os.environ.get("SECRET_KEY") or "").encode()
    digest = hashlib.sha256(secret).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_totp_secret(plain_secret: str) -> str:
    """Cifra il segreto TOTP a riposo (Fernet da SECRET_KEY)."""
    return _fernet().encrypt(plain_secret.encode()).decode()


def decrypt_totp_secret(cipher_text: str) -> str:
    """Decifra il segreto TOTP."""
    return _fernet().decrypt(cipher_text.encode()).decode()


def write_auth_log(
    db: Session,
    event: str,
    id_user: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    extra_data: Optional[dict] = None,
) -> None:
    """Scrive una riga in auth_logs (audit autenticazione)."""
    from src.models.auth_log import AuthLog

    db.add(
        AuthLog(
            id_user=id_user,
            event=event,
            ip_address=ip_address,
            user_agent=user_agent,
            extra_data=extra_data,
            created_at=datetime.now(),
        )
    )
    db.commit()


def user_is_login_eligible(user: User) -> bool:
    """Utente attivo e non soft-deleted."""
    if not user or not user.is_active:
        return False
    if getattr(user, "deleted_at", None) is not None:
        return False
    return True


def mfa_is_active(user: User) -> bool:
    """True se l'utente ha un metodo 2FA attivo sul login."""
    method = getattr(user, "mfa_method", None) or "none"
    if isinstance(method, str):
        return method in ("totp", "email")
    return str(method) in ("totp", "email")


def invalidate_user_mfa_sessions(user_id: int, db: Session) -> None:
    """Consuma tutte le sessioni MFA ancora aperte dell'utente."""
    from src.models.mfa_pending_session import MFAPendingSession

    sessions = (
        db.query(MFAPendingSession)
        .filter(
            MFAPendingSession.id_user == user_id,
            MFAPendingSession.used_at.is_(None),
        )
        .all()
    )
    now = datetime.now()
    for session in sessions:
        session.used_at = now
    if sessions:
        db.commit()


def create_mfa_pending_session(
    user_id: int,
    mfa_method: str,
    db: Session,
    ip_address: Optional[str] = None,
    otp_code: Optional[str] = None,
) -> tuple:
    """
    Crea una sessione MFA intermedia.
    Restituisce (raw_token, expires_at).
    """
    from src.models.mfa_pending_session import MFAPendingSession

    invalidate_user_mfa_sessions(user_id, db)

    raw_token = secrets.token_urlsafe(64)
    expires_at = datetime.now() + timedelta(minutes=MFA_TTL_MINUTES)
    otp_hash = _hash_opaque_token(otp_code) if otp_code else None

    session = MFAPendingSession(
        id_user=user_id,
        token_hash=_hash_opaque_token(raw_token),
        expires_at=expires_at,
        ip_address=ip_address,
        created_at=datetime.now(),
        mfa_method=mfa_method,
        otp_code_hash=otp_hash,
        failed_attempts=0,
    )
    db.add(session)
    db.commit()
    return raw_token, expires_at


def get_mfa_pending_session(raw_token: str, db: Session):
    """Carica una sessione MFA valida dal token opaco. Altrimenti None."""
    from src.models.mfa_pending_session import MFAPendingSession

    token_hash = _hash_opaque_token(raw_token)
    session = (
        db.query(MFAPendingSession)
        .filter(MFAPendingSession.token_hash == token_hash)
        .first()
    )
    if not session or not session.is_valid:
        return None
    if (session.failed_attempts or 0) >= MFA_MAX_ATTEMPTS:
        return None
    return session


def get_latest_valid_email_mfa_session(user_id: int, db: Session):
    """Ultima sessione email MFA ancora valida (setup/confirm o login)."""
    from src.models.mfa_pending_session import MFAPendingSession

    session = (
        db.query(MFAPendingSession)
        .filter(
            MFAPendingSession.id_user == user_id,
            MFAPendingSession.mfa_method == "email",
            MFAPendingSession.used_at.is_(None),
            MFAPendingSession.expires_at > datetime.now(),
        )
        .order_by(MFAPendingSession.created_at.desc())
        .first()
    )
    if not session:
        return None
    if (session.failed_attempts or 0) >= MFA_MAX_ATTEMPTS:
        return None
    return session


def generate_email_otp() -> str:
    """OTP numerico a 6 cifre."""
    upper = 10 ** MFA_OTP_LENGTH
    return f"{secrets.randbelow(upper):0{MFA_OTP_LENGTH}d}"


def verify_email_otp_hash(otp_code_hash: Optional[str], code: str) -> bool:
    if not otp_code_hash or not code:
        return False
    return secrets.compare_digest(otp_code_hash, _hash_opaque_token(code.strip()))


def verify_totp_for_user(user: User, code: str) -> bool:
    if not user.totp_secret or not code:
        return False
    try:
        plain = decrypt_totp_secret(user.totp_secret)
    except Exception:
        return False
    totp = pyotp.TOTP(plain)
    return bool(totp.verify(code.strip(), valid_window=1))


def build_totp_provisioning(user: User, plain_secret: str) -> str:
    totp = pyotp.TOTP(plain_secret)
    account = user.email or user.username
    return totp.provisioning_uri(name=account, issuer_name=TOTP_ISSUER)


def issue_session_tokens(
    user: User,
    db: Session,
    ip_address: Optional[str] = None,
) -> dict:
    """Emette access_token + refresh_token per un utente autenticato."""
    from src.models.role import PermissionType

    role = user.roles[0] if user.roles else None
    role_name = role.name if role else "USER"
    role_type = role.permission_type.value if role else PermissionType.custom.value

    access_token = create_access_token(
        username=user.username,
        user_id=user.id_user,
        role_name=role_name,
        role_type=role_type,
        expires_delta=timedelta(minutes=30),
    )
    refresh_token = create_refresh_token(
        user_id=user.id_user,
        db=db,
        device_info=None,
        ip_address=ip_address,
    )
    expires_at = datetime.now() + timedelta(minutes=30)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "current_user": user.username,
        "expires_at": expires_at,
        "mfa_required": False,
    }


def register_mfa_failure(session, db: Session) -> None:
    """Incrementa failed_attempts; consuma la sessione al tetto."""
    session.failed_attempts = (session.failed_attempts or 0) + 1
    if session.failed_attempts >= MFA_MAX_ATTEMPTS:
        session.consume()
    db.commit()


async def send_mfa_otp_email(db: Session, user: User, code: str) -> None:
    """Invia OTP 2FA via SMTP configurato. Non logga il codice."""
    from src.services.email.sender import EmailSender, EmailSendError
    from src.services.email.settings import (
        is_email_enabled,
        load_email_settings,
        smtp_ready,
    )

    settings = load_email_settings(db)
    if not is_email_enabled(settings) or not smtp_ready(settings):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMTP non configurato o email disabilitate",
        )
    if not user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'utente non ha un indirizzo email",
        )

    subject = f"{TOTP_ISSUER} — codice di verifica"
    body_text = (
        f"Il tuo codice di verifica è: {code}\n"
        f"Scade in {MFA_TTL_MINUTES} minuti.\n"
        "Se non hai richiesto questo codice, ignora il messaggio."
    )
    body_html = (
        f"<p>Il tuo codice di verifica è: <strong>{code}</strong></p>"
        f"<p>Scade in {MFA_TTL_MINUTES} minuti.</p>"
        "<p>Se non hai richiesto questo codice, ignora il messaggio.</p>"
    )
    try:
        await EmailSender(settings).send(
            to=user.email,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
        )
    except EmailSendError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invio email OTP fallito: {exc}",
        ) from exc


def clear_user_mfa(user: User, db: Session) -> None:
    """Disattiva completamente il 2FA sull'utente."""
    user.mfa_method = "none"
    user.totp_enabled = False
    user.totp_secret = None
    invalidate_user_mfa_sessions(user.id_user, db)
    db.commit()



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