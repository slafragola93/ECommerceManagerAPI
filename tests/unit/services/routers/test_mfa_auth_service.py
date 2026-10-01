"""
Test unitari per helper MFA / 2FA in auth_service.
"""
from datetime import datetime

import pyotp
import pytest

from src.models.user import User
from src.models.mfa_pending_session import MFAPendingSession
from src.models.auth_log import AuthLog
from src.services.routers.auth_service import (
    bcrypt_context,
    encrypt_totp_secret,
    decrypt_totp_secret,
    create_mfa_pending_session,
    get_mfa_pending_session,
    generate_email_otp,
    verify_email_otp_hash,
    verify_totp_for_user,
    register_mfa_failure,
    clear_user_mfa,
    write_auth_log,
    mfa_is_active,
    user_is_login_eligible,
    MFA_MAX_ATTEMPTS,
    _hash_opaque_token,
)


@pytest.fixture(autouse=True)
def _secret_key(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-mfa-unit-tests")


def _make_user(db_session, **kwargs) -> User:
    data = {
        "username": kwargs.get("username", "mfa_user"),
        "email": kwargs.get("email", "mfa@example.com"),
        "firstname": "Mfa",
        "lastname": "User",
        "password": bcrypt_context.hash("password12"),
        "is_active": True,
        "mfa_method": kwargs.get("mfa_method", "none"),
        "totp_enabled": kwargs.get("totp_enabled", False),
        "totp_secret": kwargs.get("totp_secret"),
    }
    user = User(**data)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.unit
class TestMfaCrypto:
    def test_encrypt_decrypt_roundtrip(self):
        plain = pyotp.random_base32()
        cipher = encrypt_totp_secret(plain)
        assert cipher != plain
        assert decrypt_totp_secret(cipher) == plain

    def test_secret_not_plaintext_in_cipher(self):
        plain = "JBSWY3DPEHPK3PXP"
        cipher = encrypt_totp_secret(plain)
        assert plain not in cipher


@pytest.mark.unit
class TestMfaPendingSession:
    def test_create_and_get_session(self, db_session):
        user = _make_user(db_session)
        raw, expires = create_mfa_pending_session(
            user.id_user, "totp", db_session, otp_code=None
        )
        assert raw
        assert expires > datetime.now()
        session = get_mfa_pending_session(raw, db_session)
        assert session is not None
        assert session.id_user == user.id_user
        assert session.mfa_method == "totp"

    def test_email_otp_hash_compare(self, db_session):
        user = _make_user(db_session)
        code = "123456"
        raw, _ = create_mfa_pending_session(
            user.id_user, "email", db_session, otp_code=code
        )
        session = get_mfa_pending_session(raw, db_session)
        assert verify_email_otp_hash(session.otp_code_hash, code)
        assert not verify_email_otp_hash(session.otp_code_hash, "000000")

    def test_lock_after_max_failures(self, db_session):
        user = _make_user(db_session)
        raw, _ = create_mfa_pending_session(user.id_user, "totp", db_session)
        session = get_mfa_pending_session(raw, db_session)
        for _ in range(MFA_MAX_ATTEMPTS):
            register_mfa_failure(session, db_session)
            session = (
                db_session.query(MFAPendingSession)
                .filter(MFAPendingSession.token_hash == _hash_opaque_token(raw))
                .first()
            )
        assert session.used_at is not None
        assert get_mfa_pending_session(raw, db_session) is None

    def test_invalidate_previous_on_new_login(self, db_session):
        user = _make_user(db_session)
        raw1, _ = create_mfa_pending_session(user.id_user, "totp", db_session)
        raw2, _ = create_mfa_pending_session(user.id_user, "totp", db_session)
        assert get_mfa_pending_session(raw1, db_session) is None
        assert get_mfa_pending_session(raw2, db_session) is not None


@pytest.mark.unit
class TestTotpVerify:
    def test_verify_totp_for_user(self, db_session):
        plain = pyotp.random_base32()
        user = _make_user(
            db_session,
            totp_secret=encrypt_totp_secret(plain),
            totp_enabled=True,
            mfa_method="totp",
        )
        code = pyotp.TOTP(plain).now()
        assert verify_totp_for_user(user, code)
        assert not verify_totp_for_user(user, "000000")


@pytest.mark.unit
class TestMfaHelpers:
    def test_generate_email_otp_length(self):
        code = generate_email_otp()
        assert len(code) == 6
        assert code.isdigit()

    def test_mfa_is_active(self, db_session):
        user = _make_user(db_session, mfa_method="none")
        assert not mfa_is_active(user)
        user.mfa_method = "totp"
        assert mfa_is_active(user)

    def test_user_not_eligible_when_deleted(self, db_session):
        user = _make_user(db_session)
        user.deleted_at = datetime.now()
        db_session.commit()
        assert not user_is_login_eligible(user)

    def test_clear_user_mfa(self, db_session):
        plain = pyotp.random_base32()
        user = _make_user(
            db_session,
            mfa_method="totp",
            totp_enabled=True,
            totp_secret=encrypt_totp_secret(plain),
        )
        clear_user_mfa(user, db_session)
        db_session.refresh(user)
        assert user.mfa_method == "none"
        assert user.totp_enabled is False
        assert user.totp_secret is None

    def test_write_auth_log(self, db_session):
        user = _make_user(db_session)
        write_auth_log(
            db_session,
            event="mfa_success",
            id_user=user.id_user,
            extra_data={"method": "totp"},
        )
        row = db_session.query(AuthLog).filter(AuthLog.id_user == user.id_user).first()
        assert row is not None
        assert row.event == "mfa_success"
