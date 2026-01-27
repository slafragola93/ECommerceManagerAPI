"""
Helper per autenticazione nei test
"""
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
from jose import jwt
from fastapi import Header


# Secret key per i test (dovrebbe essere la stessa dell'app)
TEST_SECRET_KEY = os.environ.get("SECRET_KEY", "test-secret-key-for-jwt-tokens")


def create_test_token(
    username: str = "testuser",
    user_id: int = 1,
    roles: List[Dict[str, Any]] = None,
    expires_delta: timedelta = None
) -> str:
    """
    Crea un token JWT per i test.
    
    Args:
        username: Nome utente
        user_id: ID utente
        roles: Lista di ruoli con permessi
        expires_delta: Durata del token (default: 1 anno)
    
    Returns:
        Token JWT codificato
    """
    if roles is None:
        roles = [{"name": "USER", "permissions": ["R"]}]
    
    if expires_delta is None:
        expires_delta = timedelta(days=365)
    
    payload = {
        "sub": username,
        "id": user_id,
        "roles": roles,
        "exp": datetime.utcnow() + expires_delta
    }
    
    return jwt.encode(payload, TEST_SECRET_KEY, algorithm="HS256")


def create_admin_token(user_id: int = 1) -> str:
    """Crea un token per utente admin"""
    return create_test_token(
        username="admin",
        user_id=user_id,
        roles=[{"name": "ADMIN", "permissions": ["C", "R", "U", "D"]}]
    )


def create_ordini_token(user_id: int = 2) -> str:
    """Crea un token per utente con ruolo ORDINI"""
    return create_test_token(
        username="ordini_user",
        user_id=user_id,
        roles=[{"name": "ORDINI", "permissions": ["C", "R", "U", "D"]}]
    )


def create_user_token(user_id: int = 3) -> str:
    """Crea un token per utente base"""
    return create_test_token(
        username="user",
        user_id=user_id,
        roles=[{"name": "USER", "permissions": ["R"]}]
    )


def get_auth_headers(token: str) -> Dict[str, str]:
    """
    Crea header di autenticazione per le richieste HTTP.
    
    Args:
        token: Token JWT
    
    Returns:
        Dict con header Authorization
    """
    return {"Authorization": f"Bearer {token}"}


def get_admin_headers() -> Dict[str, str]:
    """Ritorna header per utente admin"""
    token = create_admin_token()
    return get_auth_headers(token)


def get_ordini_headers() -> Dict[str, str]:
    """Ritorna header per utente ordini"""
    token = create_ordini_token()
    return get_auth_headers(token)


def get_user_headers() -> Dict[str, str]:
    """Ritorna header per utente base"""
    token = create_user_token()
    return get_auth_headers(token)
