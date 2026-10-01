from datetime import datetime, timedelta
from typing import Annotated, Union
import os

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from src.models.role import PermissionType
from src.models.user import User
from src.schemas.user_schema import (
    UserSchema,
    Token,
    MFAChallengeResponse,
    MFAVerifySchema,
    MFAResendSchema,
    MFASetupSchema,
    MFAConfirmSchema,
    MFADisableSchema,
    MFAStatusResponse,
    MFASetupResponse,
)
from src.services.routers.auth_service import (
    authenticate_user,
    bcrypt_context,
    create_access_token,
    verify_refresh_token,
    revoke_refresh_token,
    revoke_all_user_tokens,
    get_current_user,
    user_is_login_eligible,
    mfa_is_active,
    create_mfa_pending_session,
    get_mfa_pending_session,
    get_latest_valid_email_mfa_session,
    generate_email_otp,
    verify_email_otp_hash,
    verify_totp_for_user,
    build_totp_provisioning,
    encrypt_totp_secret,
    issue_session_tokens,
    register_mfa_failure,
    send_mfa_otp_email,
    clear_user_mfa,
    write_auth_log,
    invalidate_user_mfa_sessions,
    MFA_RESEND_COOLDOWN_SECONDS,
)
from src.core.dependencies import db_dependency
from src.core.exceptions import (
    ValidationException,
    AuthenticationException,
)
from src.events.core.event import Event, EventType
from src.events.runtime import emit_event
from src.core.request_context import get_ip_address, get_request_id, set_actor
import pyotp

load_dotenv()

router = APIRouter(
    prefix='/api/v1/auth',
    tags=['Authentication'],
)

SECRET_KEY = os.environ.get("SECRET_KEY")


def _generic_mfa_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Codice non valido o sessione scaduta",
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def create_user(db: db_dependency, us: UserSchema):
    """Crea un nuovo utente nel sistema."""
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


@router.post(
    "/login",
    response_model=Union[Token, MFAChallengeResponse],
    status_code=status.HTTP_200_OK,
)
async def get_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: db_dependency
):
    """Autentica un utente. Con 2FA attivo restituisce mfa_token invece dei token di sessione."""

    user = authenticate_user(db, form_data.username, form_data.password)
    if not user or not user_is_login_eligible(user):
        emit_event(
            Event(
                event_type=EventType.AUTH_LOGIN_FAILED.value,
                data={
                    "username": form_data.username,
                    "status": "failure",
                },
                metadata={
                    "actor_id": None,
                    "actor_username": form_data.username,
                    "actor_role": "",
                    "status": "failure",
                    "ip_address": get_ip_address(),
                    "request_id": get_request_id(),
                },
            )
        )
        raise AuthenticationException("Credenziali non valide")

    ip = get_ip_address()

    if mfa_is_active(user):
        method = str(user.mfa_method)
        otp_code = generate_email_otp() if method == "email" else None

        # Sessione prima dell'email: se il DB fallisce non si spamma OTP
        mfa_token, expires_at = create_mfa_pending_session(
            user_id=user.id_user,
            mfa_method=method,
            db=db,
            ip_address=ip,
            otp_code=otp_code,
        )
        if method == "email":
            try:
                await send_mfa_otp_email(db, user, otp_code)
            except Exception:
                invalidate_user_mfa_sessions(user.id_user, db)
                raise

        return MFAChallengeResponse(
            mfa_required=True,
            mfa_token=mfa_token,
            mfa_method=method,
            expires_at=expires_at,
        )

    role = user.roles[0] if user.roles else None
    role_name = role.name if role else "USER"
    set_actor(actor_id=user.id_user, username=user.username, role=role_name)

    tokens = issue_session_tokens(user, db, ip_address=ip)

    emit_event(
        Event(
            event_type=EventType.AUTH_LOGIN_SUCCESS.value,
            data={
                "id_user": user.id_user,
                "username": user.username,
            },
            metadata={
                "actor_id": user.id_user,
                "actor_username": user.username,
                "actor_role": role_name,
            },
        )
    )

    return Token(**tokens)


@router.post("/mfa/verify", response_model=Token, status_code=status.HTTP_200_OK)
async def mfa_verify(payload: MFAVerifySchema, db: db_dependency):
    """Verifica il codice 2FA e emette access_token + refresh_token."""
    session = get_mfa_pending_session(payload.mfa_token, db)
    if not session:
        raise _generic_mfa_error()

    user = db.query(User).filter(User.id_user == session.id_user).first()
    if not user or not user_is_login_eligible(user):
        session.consume()
        db.commit()
        raise _generic_mfa_error()

    method = str(session.mfa_method)
    code_ok = False
    if method == "totp":
        code_ok = verify_totp_for_user(user, payload.code)
    elif method == "email":
        code_ok = verify_email_otp_hash(session.otp_code_hash, payload.code)

    if not code_ok:
        register_mfa_failure(session, db)
        write_auth_log(
            db,
            event=EventType.AUTH_MFA_FAILED.value,
            id_user=user.id_user,
            ip_address=get_ip_address(),
            extra_data={"method": method},
        )
        emit_event(
            Event(
                event_type=EventType.AUTH_MFA_FAILED.value,
                data={"id_user": user.id_user, "method": method},
                metadata={
                    "actor_id": user.id_user,
                    "actor_username": user.username,
                },
            )
        )
        raise _generic_mfa_error()

    session.consume()
    db.commit()

    write_auth_log(
        db,
        event=EventType.AUTH_MFA_SUCCESS.value,
        id_user=user.id_user,
        ip_address=get_ip_address(),
        extra_data={"method": method},
    )
    emit_event(
        Event(
            event_type=EventType.AUTH_MFA_SUCCESS.value,
            data={"id_user": user.id_user, "method": method},
            metadata={
                "actor_id": user.id_user,
                "actor_username": user.username,
            },
        )
    )

    role = user.roles[0] if user.roles else None
    role_name = role.name if role else "USER"
    set_actor(actor_id=user.id_user, username=user.username, role=role_name)

    tokens = issue_session_tokens(user, db, ip_address=get_ip_address())
    emit_event(
        Event(
            event_type=EventType.AUTH_LOGIN_SUCCESS.value,
            data={"id_user": user.id_user, "username": user.username},
            metadata={
                "actor_id": user.id_user,
                "actor_username": user.username,
                "actor_role": role_name,
            },
        )
    )
    return Token(**tokens)


@router.post("/mfa/resend", status_code=status.HTTP_200_OK)
async def mfa_resend(payload: MFAResendSchema, db: db_dependency):
    """Reinvia OTP email (solo method=email), cooldown 60s."""
    session = get_mfa_pending_session(payload.mfa_token, db)
    if not session or str(session.mfa_method) != "email":
        raise _generic_mfa_error()

    elapsed = (datetime.now() - session.created_at).total_seconds()
    if elapsed < MFA_RESEND_COOLDOWN_SECONDS:
        wait = int(MFA_RESEND_COOLDOWN_SECONDS - elapsed)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Attendi {wait} secondi prima di richiedere un nuovo codice",
        )

    user = db.query(User).filter(User.id_user == session.id_user).first()
    if not user or not user_is_login_eligible(user):
        raise _generic_mfa_error()

    otp_code = generate_email_otp()
    mfa_token, expires_at = create_mfa_pending_session(
        user_id=user.id_user,
        mfa_method="email",
        db=db,
        ip_address=get_ip_address(),
        otp_code=otp_code,
    )
    try:
        await send_mfa_otp_email(db, user, otp_code)
    except Exception:
        invalidate_user_mfa_sessions(user.id_user, db)
        raise
    return {
        "mfa_required": True,
        "mfa_token": mfa_token,
        "mfa_method": "email",
        "expires_at": expires_at,
        "message": "Nuovo codice inviato",
    }


@router.get("/2fa/status", response_model=MFAStatusResponse, status_code=status.HTTP_200_OK)
async def mfa_status(
    db: db_dependency,
    current_user: dict = Depends(get_current_user),
):
    """Stato 2FA dell'utente autenticato."""
    user = db.query(User).filter(User.id_user == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente non trovato")
    return MFAStatusResponse(
        mfa_method=str(user.mfa_method or "none"),
        totp_enabled=bool(user.totp_enabled),
    )


@router.post("/2fa/setup", response_model=MFASetupResponse, status_code=status.HTTP_200_OK)
async def mfa_setup(
    payload: MFASetupSchema,
    db: db_dependency,
    current_user: dict = Depends(get_current_user),
):
    """Avvia l'attivazione 2FA (TOTP o email). Richiede /2fa/confirm."""
    user = db.query(User).filter(User.id_user == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente non trovato")

    if mfa_is_active(user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="2FA già attivo: disattivalo prima di riconfigurarlo",
        )

    method = payload.method

    if method == "totp":
        plain_secret = pyotp.random_base32()
        user.totp_secret = encrypt_totp_secret(plain_secret)
        user.totp_enabled = False
        # mfa_method resta 'none' fino a confirm
        invalidate_user_mfa_sessions(user.id_user, db)
        db.commit()
        return MFASetupResponse(
            method="totp",
            otpauth_uri=build_totp_provisioning(user, plain_secret),
            totp_secret=plain_secret,
            message="Scansiona il QR o inserisci il segreto, poi conferma con POST /2fa/confirm",
        )

    # email
    user.totp_secret = None
    user.totp_enabled = False
    db.commit()

    otp_code = generate_email_otp()
    create_mfa_pending_session(
        user_id=user.id_user,
        mfa_method="email",
        db=db,
        ip_address=get_ip_address(),
        otp_code=otp_code,
    )
    try:
        await send_mfa_otp_email(db, user, otp_code)
    except Exception:
        invalidate_user_mfa_sessions(user.id_user, db)
        raise
    return MFASetupResponse(
        method="email",
        message="Codice inviato all'email dell'utente. Conferma con POST /2fa/confirm",
    )


@router.post("/2fa/confirm", status_code=status.HTTP_200_OK)
async def mfa_confirm(
    payload: MFAConfirmSchema,
    db: db_dependency,
    current_user: dict = Depends(get_current_user),
):
    """Conferma e attiva il 2FA dopo /2fa/setup."""
    user = db.query(User).filter(User.id_user == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente non trovato")

    if mfa_is_active(user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="2FA già attivo",
        )

    # Pending TOTP setup: secret presente, method ancora none
    if user.totp_secret and not user.totp_enabled:
        if not verify_totp_for_user(user, payload.code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Codice TOTP non valido",
            )
        user.totp_enabled = True
        user.mfa_method = "totp"
        invalidate_user_mfa_sessions(user.id_user, db)
        db.commit()
        write_auth_log(
            db,
            event=EventType.AUTH_MFA_ENABLED.value,
            id_user=user.id_user,
            ip_address=get_ip_address(),
            extra_data={"method": "totp"},
        )
        emit_event(
            Event(
                event_type=EventType.AUTH_MFA_ENABLED.value,
                data={"id_user": user.id_user, "method": "totp"},
                metadata={
                    "actor_id": user.id_user,
                    "actor_username": user.username,
                },
            )
        )
        return {"message": "2FA TOTP attivato", "mfa_method": "totp"}

    # Pending email setup
    session = get_latest_valid_email_mfa_session(user.id_user, db)
    if session and verify_email_otp_hash(session.otp_code_hash, payload.code):
        session.consume()
        user.mfa_method = "email"
        user.totp_enabled = False
        user.totp_secret = None
        db.commit()
        write_auth_log(
            db,
            event=EventType.AUTH_MFA_ENABLED.value,
            id_user=user.id_user,
            ip_address=get_ip_address(),
            extra_data={"method": "email"},
        )
        emit_event(
            Event(
                event_type=EventType.AUTH_MFA_ENABLED.value,
                data={"id_user": user.id_user, "method": "email"},
                metadata={
                    "actor_id": user.id_user,
                    "actor_username": user.username,
                },
            )
        )
        return {"message": "2FA email attivato", "mfa_method": "email"}

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Nessun setup 2FA in corso o codice non valido",
    )


@router.post("/2fa/disable", status_code=status.HTTP_200_OK)
async def mfa_disable(
    payload: MFADisableSchema,
    db: db_dependency,
    current_user: dict = Depends(get_current_user),
):
    """Disattiva il 2FA: richiede password attuale e codice valido."""
    user = db.query(User).filter(User.id_user == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente non trovato")

    if not mfa_is_active(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA non attivo",
        )

    if not bcrypt_context.verify(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password non valida",
        )

    method = str(user.mfa_method)
    code_ok = False
    if method == "totp":
        code_ok = verify_totp_for_user(user, payload.code)
    elif method == "email":
        session = get_latest_valid_email_mfa_session(user.id_user, db)
        if not session:
            otp_code = generate_email_otp()
            create_mfa_pending_session(
                user_id=user.id_user,
                mfa_method="email",
                db=db,
                ip_address=get_ip_address(),
                otp_code=otp_code,
            )
            try:
                await send_mfa_otp_email(db, user, otp_code)
            except Exception:
                invalidate_user_mfa_sessions(user.id_user, db)
                raise
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Codice inviato via email. Ripeti la richiesta con password e codice ricevuto.",
            )
        code_ok = verify_email_otp_hash(session.otp_code_hash, payload.code)
        if code_ok:
            session.consume()
            db.commit()
        else:
            register_mfa_failure(session, db)

    if not code_ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codice non valido",
        )

    clear_user_mfa(user, db)
    write_auth_log(
        db,
        event=EventType.AUTH_MFA_DISABLED.value,
        id_user=user.id_user,
        ip_address=get_ip_address(),
        extra_data={"method": method},
    )
    emit_event(
        Event(
            event_type=EventType.AUTH_MFA_DISABLED.value,
            data={"id_user": user.id_user, "method": method},
            metadata={
                "actor_id": user.id_user,
                "actor_username": user.username,
            },
        )
    )
    return {"message": "2FA disattivato", "mfa_method": "none"}


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

    refresh = verify_refresh_token(raw_token, db)

    user = db.query(User).filter(
        User.id_user == refresh.id_user
    ).first()

    if not user or not user_is_login_eligible(user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utente non trovato o disattivato"
        )

    role = user.roles[0] if user.roles else None
    role_name = role.name if role else "USER"
    role_type = role.permission_type.value if role else PermissionType.custom.value

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
    emit_event(
        Event(
            event_type=EventType.AUTH_LOGOUT.value,
            data={"scope": "single"},
            metadata={},
        )
    )

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
    emit_event(
        Event(
            event_type=EventType.AUTH_LOGOUT.value,
            data={
                "id_user": user_id,
                "scope": "all",
                "tokens_revoked": count,
            },
            metadata={},
        )
    )
    return {"message": f"Logout effettuato da tutti i dispositivi", "tokens_revoked": count}
