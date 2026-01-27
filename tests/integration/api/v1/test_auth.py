"""
Test per endpoint di autenticazione
"""
import pytest
from fastapi import status
from httpx import AsyncClient
from tests.helpers.asserts import assert_success_response, assert_error_response
from tests.helpers.auth import create_test_token, get_auth_headers


@pytest.mark.integration
class TestAuth:
    """Test per /api/v1/auth/*"""
    
    @pytest.mark.asyncio
    async def test_login_success(self, async_client: AsyncClient, db_session):
        """
        Test: Login con credenziali valide
        
        Arrange: Utente esistente nel database
        Act: POST /api/v1/auth/login
        Assert: Status 200, token presente, current_user presente
        """
        # TODO: Creare utente nel database prima del test
        # Per ora questo è uno skeleton
        
        login_data = {
            "username": "usertest",
            "password": "passwordtest"
        }
        
        response = await async_client.post("/api/v1/auth/login", data=login_data)
        
        # Assert
        assert_success_response(response, status_code=status.HTTP_200_OK)
        data = response.json()
        assert "access_token" in data
        assert "current_user" in data
        assert data["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, async_client: AsyncClient):
        """
        Test: Login con credenziali non valide
        
        Arrange: Nessun setup necessario
        Act: POST /api/v1/auth/login con credenziali sbagliate
        Assert: Status 401
        """
        login_data = {
            "username": "invalid_user",
            "password": "wrong_password"
        }
        
        response = await async_client.post("/api/v1/auth/login", data=login_data)
        
        # Assert
        assert_error_response(response, status_code=status.HTTP_401_UNAUTHORIZED)
    
    @pytest.mark.asyncio
    async def test_get_current_user_with_valid_token(self, async_client: AsyncClient):
        """
        Test: Get current user con token valido
        
        Arrange: Token JWT valido
        Act: GET /api/v1/auth/me (o endpoint equivalente)
        Assert: Status 200, dati utente corretti
        """
        # TODO: Implementare quando l'endpoint è disponibile
        token = create_test_token(username="testuser", user_id=1)
        headers = get_auth_headers(token)
        
        # Se esiste un endpoint /me o simile
        # response = await async_client.get("/api/v1/auth/me", headers=headers)
        # assert_success_response(response)
        # data = response.json()
        # assert data["username"] == "testuser"
        
        pytest.skip("Endpoint /me non ancora implementato")
    
    @pytest.mark.asyncio
    async def test_get_current_user_with_invalid_token(self, async_client: AsyncClient):
        """
        Test: Get current user con token non valido
        
        Arrange: Token JWT non valido
        Act: GET /api/v1/auth/me con token invalido
        Assert: Status 401
        """
        headers = {"Authorization": "Bearer invalid_token"}
        
        # Se esiste un endpoint /me o simile
        # response = await async_client.get("/api/v1/auth/me", headers=headers)
        # assert_error_response(response, status_code=status.HTTP_401_UNAUTHORIZED)
        
        pytest.skip("Endpoint /me non ancora implementato")
