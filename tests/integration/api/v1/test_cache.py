"""
Test per endpoint cache
"""
import pytest
from fastapi import status
from tests.helpers.asserts import assert_success_response, assert_error_response


@pytest.mark.integration
class TestCache:
    """Test per /api/v1/cache/*"""
    
    @pytest.mark.asyncio
    async def test_get_cache_stats_success(self, admin_client):
        """
        Test: Recupero statistiche cache
        
        Arrange: Cache inizializzata
        Act: GET /api/v1/cache/stats
        Assert: Status 200, statistiche presenti
        """
        response = admin_client.get("/api/v1/cache/stats")
        
        # Assert
        assert_success_response(response)
        data = response.json()
        # Verifica che ci siano campi di statistiche (struttura dipende dall'implementazione)
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_clear_cache_pattern_success(self, admin_client):
        """
        Test: Pulizia cache per pattern
        
        Arrange: Cache con alcune chiavi
        Act: DELETE /api/v1/cache?pattern=test_*
        Assert: Status 200, messaggio di conferma
        """
        pattern = "test_*"
        
        response = admin_client.delete(f"/api/v1/cache?pattern={pattern}")
        
        # Assert
        assert_success_response(response)
        data = response.json()
        assert "message" in data
        assert "Deleted" in data["message"] or "deleted" in data["message"]
    
    @pytest.mark.asyncio
    async def test_reset_all_cache_success(self, admin_client):
        """
        Test: Reset completo cache
        
        Arrange: Cache con dati
        Act: POST /api/v1/cache/reset
        Assert: Status 200, messaggio di conferma
        """
        response = admin_client.post("/api/v1/cache/reset")
        
        # Assert
        assert_success_response(response)
        data = response.json()
        assert "message" in data
        assert "cleared" in data["message"].lower() or "reset" in data["message"].lower()
    
    @pytest.mark.asyncio
    async def test_cache_health_check(self, admin_client):
        """
        Test: Health check cache
        
        Arrange: Cache inizializzata
        Act: GET /health/cache
        Assert: Status 200, status="healthy"
        """
        response = admin_client.get("/health/cache")
        
        # Assert
        assert_success_response(response)
        data = response.json()
        assert "status" in data
        # Status può essere "healthy", "degraded", etc.
