"""
Test integration per autenticazione e 2FA.
"""
from unittest.mock import AsyncMock, patch

import pyotp
import pytest
from fastapi import status
from httpx import AsyncClient

from tests.helpers.asserts import assert_success_response, assert_error_response
from tests.helpers.auth import create_test_token, get_auth_headers
from src.services.routers.auth_service import (
    bcrypt_context,
    encrypt_totp_secret,
    create_access_token,
)


def _create_user(db_session, username="usertest", email="usertest@example.com", **kwargs):
    from src.models.user import User

    user = User(
        username=username,
        email=email,
        firstname="User",
        lastname="Test",
        password=bcrypt_context.hash(kwargs.get("password", "passwordtest")),
        is_active=True,
        mfa_method=kwargs.get("mfa_method", "none"),
        totp_enabled=kwargs.get("totp_enabled", False),
        totp_secret=kwargs.get("totp_secret"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _bearer_for_user(user):
    token = create_access_token(
        username=user.username,
        user_id=user.id_user,
        role_name="USER",
        role_type="custom",
    )
    return get_auth_headers(token)


@pytest.mark.integration
class TestAuth:
    """Test per /api/v1/auth/*"""

    @pytest.mark.asyncio
    async def test_login_success(self, async_client: AsyncClient, db_session):
        _create_user(db_session)

        response = await async_client.post(
            "/api/v1/auth/login",
            data={"username": "usertest", "password": "passwordtest"},
        )

        assert_success_response(response, status_code=status.HTTP_200_OK)
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "current_user" in data
        assert data["token_type"] == "bearer"
        assert data.get("mfa_required") is False

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, async_client: AsyncClient):
        response = await async_client.post(
            "/api/v1/auth/login",
            data={"username": "invalid_user", "password": "wrong_password"},
        )
        assert_error_response(response, status_code=status.HTTP_401_UNAUTHORIZED)

    @pytest.mark.asyncio
    async def test_login_with_totp_returns_mfa_challenge(
        self, async_client: AsyncClient, db_session
    ):
        plain = pyotp.random_base32()
        _create_user(
            db_session,
            mfa_method="totp",
            totp_enabled=True,
            totp_secret=encrypt_totp_secret(plain),
        )

        response = await async_client.post(
            "/api/v1/auth/login",
            data={"username": "usertest", "password": "passwordtest"},
        )

        assert_success_response(response, status_code=status.HTTP_200_OK)
        data = response.json()
        assert data["mfa_required"] is True
        assert data["mfa_method"] == "totp"
        assert "mfa_token" in data
        assert "access_token" not in data

    @pytest.mark.asyncio
    async def test_mfa_verify_totp_success(self, async_client: AsyncClient, db_session):
        plain = pyotp.random_base32()
        _create_user(
            db_session,
            mfa_method="totp",
            totp_enabled=True,
            totp_secret=encrypt_totp_secret(plain),
        )

        login = await async_client.post(
            "/api/v1/auth/login",
            data={"username": "usertest", "password": "passwordtest"},
        )
        mfa_token = login.json()["mfa_token"]
        code = pyotp.TOTP(plain).now()

        verify = await async_client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_token": mfa_token, "code": code},
        )
        assert_success_response(verify, status_code=status.HTTP_200_OK)
        data = verify.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data.get("mfa_required") is False

    @pytest.mark.asyncio
    async def test_mfa_verify_wrong_code(self, async_client: AsyncClient, db_session):
        plain = pyotp.random_base32()
        _create_user(
            db_session,
            mfa_method="totp",
            totp_enabled=True,
            totp_secret=encrypt_totp_secret(plain),
        )

        login = await async_client.post(
            "/api/v1/auth/login",
            data={"username": "usertest", "password": "passwordtest"},
        )
        mfa_token = login.json()["mfa_token"]

        verify = await async_client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_token": mfa_token, "code": "000000"},
        )
        assert_error_response(verify, status_code=status.HTTP_401_UNAUTHORIZED)

    @pytest.mark.asyncio
    async def test_mfa_lock_after_five_failures(
        self, async_client: AsyncClient, db_session
    ):
        plain = pyotp.random_base32()
        _create_user(
            db_session,
            mfa_method="totp",
            totp_enabled=True,
            totp_secret=encrypt_totp_secret(plain),
        )

        login = await async_client.post(
            "/api/v1/auth/login",
            data={"username": "usertest", "password": "passwordtest"},
        )
        mfa_token = login.json()["mfa_token"]

        for _ in range(5):
            await async_client.post(
                "/api/v1/auth/mfa/verify",
                json={"mfa_token": mfa_token, "code": "000000"},
            )

        # Anche il codice corretto non deve più funzionare
        code = pyotp.TOTP(plain).now()
        verify = await async_client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_token": mfa_token, "code": code},
        )
        assert_error_response(verify, status_code=status.HTTP_401_UNAUTHORIZED)

    @pytest.mark.asyncio
    async def test_2fa_setup_confirm_disable_totp(
        self, async_client: AsyncClient, db_session
    ):
        user = _create_user(db_session)
        headers = _bearer_for_user(user)

        setup = await async_client.post(
            "/api/v1/auth/2fa/setup",
            json={"method": "totp"},
            headers=headers,
        )
        assert_success_response(setup, status_code=status.HTTP_200_OK)
        setup_data = setup.json()
        assert setup_data["method"] == "totp"
        assert setup_data["otpauth_uri"]
        assert setup_data["totp_secret"]
        plain = setup_data["totp_secret"]

        # Segreto cifrato nel DB
        db_session.refresh(user)
        assert user.totp_secret is not None
        assert plain not in user.totp_secret
        assert str(user.mfa_method) == "none"

        confirm = await async_client.post(
            "/api/v1/auth/2fa/confirm",
            json={"code": pyotp.TOTP(plain).now()},
            headers=headers,
        )
        assert_success_response(confirm, status_code=status.HTTP_200_OK)
        db_session.refresh(user)
        assert str(user.mfa_method) == "totp"
        assert user.totp_enabled is True

        disable = await async_client.post(
            "/api/v1/auth/2fa/disable",
            json={"password": "passwordtest", "code": pyotp.TOTP(plain).now()},
            headers=headers,
        )
        assert_success_response(disable, status_code=status.HTTP_200_OK)
        db_session.refresh(user)
        assert str(user.mfa_method) == "none"
        assert user.totp_secret is None

    @pytest.mark.asyncio
    async def test_login_email_mfa_with_mocked_sender(
        self, async_client: AsyncClient, db_session
    ):
        _create_user(db_session, mfa_method="email", totp_enabled=False)

        with patch(
            "src.routers.auth.send_mfa_otp_email",
            new_callable=AsyncMock,
        ) as mock_send, patch(
            "src.routers.auth.generate_email_otp",
            return_value="654321",
        ):
            login = await async_client.post(
                "/api/v1/auth/login",
                data={"username": "usertest", "password": "passwordtest"},
            )
            assert_success_response(login, status_code=status.HTTP_200_OK)
            data = login.json()
            assert data["mfa_required"] is True
            assert data["mfa_method"] == "email"
            mock_send.assert_awaited()

            verify = await async_client.post(
                "/api/v1/auth/mfa/verify",
                json={"mfa_token": data["mfa_token"], "code": "654321"},
            )
            assert_success_response(verify, status_code=status.HTTP_200_OK)
            assert "access_token" in verify.json()

    @pytest.mark.asyncio
    async def test_get_current_user_with_valid_token(self, async_client: AsyncClient):
        token = create_test_token(username="testuser", user_id=1)
        headers = get_auth_headers(token)
        pytest.skip("Endpoint /me non ancora implementato")

    @pytest.mark.asyncio
    async def test_get_current_user_with_invalid_token(self, async_client: AsyncClient):
        headers = {"Authorization": "Bearer invalid_token"}
        pytest.skip("Endpoint /me non ancora implementato")
