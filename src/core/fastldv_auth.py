"""
Autenticazione API key per endpoint FastLDV (magazzino).
"""
from fastapi import Header, HTTPException, status

from src.core.settings import get_fastldv_settings


async def verify_fastldv_api_key(
    x_fastldv_key: str = Header(..., alias="X-FastLDV-Key"),
) -> bool:
    """Verifica header X-FastLDV-Key contro FASTLDV_API_KEY in .env."""
    settings = get_fastldv_settings()
    expected = settings.fastldv_api_key

    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FastLDV API key non configurata sul server",
        )

    if x_fastldv_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key FastLDV non valida",
        )

    return True
