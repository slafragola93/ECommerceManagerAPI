"""
Test per sincronizzazione PrestaShop
"""
import pytest
from fastapi import status
from unittest.mock import patch, AsyncMock
from tests.helpers.asserts import assert_success_response, assert_error_response


@pytest.mark.integration
class TestSyncPrestashop:
    """Test per POST /api/v1/sync/prestashop"""
    
    @pytest.mark.asyncio
    async def test_sync_prestashop_started(
        self,
        admin_client,
        db_session
    ):
        """
        Test: Avvio sincronizzazione PrestaShop
        
        Arrange: Store esistente nel database
        Act: POST /api/v1/sync/prestashop?store_id=1
        Assert: Status 202, messaggio di avvio, sync_id presente
        """
        from src.models.platform import Platform
        from src.models.store import Store

        platform = Platform(name="PrestaShop")
        db_session.add(platform)
        db_session.commit()

        store = Store(
            id_platform=platform.id_platform,
            name="Store Test",
            base_url="https://store-test.example.com",
            api_key="test-api-key",
        )
        db_session.add(store)
        db_session.commit()
        store_id = store.id_store
        
        # Mock del servizio PrestaShop per evitare chiamate HTTP reali
        with patch('src.services.ecommerce.prestashop_service.PrestaShopService') as mock_service:
            mock_instance = AsyncMock()
            mock_service.return_value.__aenter__.return_value = mock_instance
            mock_instance.sync_all_data = AsyncMock(return_value={"status": "completed"})
            
            # Act
            response = admin_client.post(
                f"/api/v1/sync/prestashop?store_id={store_id}"
            )
            
            # Assert
            assert_success_response(response, status_code=status.HTTP_202_ACCEPTED)
            data = response.json()
            assert "message" in data
            assert "sync_id" in data
            assert data["status"] == "accepted"
    
    @pytest.mark.asyncio
    async def test_sync_prestashop_store_not_found(self, admin_client):
        """
        Test: Sincronizzazione PrestaShop con store inesistente
        
        Arrange: Nessun setup
        Act: POST /api/v1/sync/prestashop?store_id=99999
        Assert: Status 404
        """
        store_id = 99999
        
        response = admin_client.post(
            f"/api/v1/sync/prestashop?store_id={store_id}"
        )
        
        # Assert
        assert_error_response(response, status_code=status.HTTP_404_NOT_FOUND)
    
    @pytest.mark.asyncio
    async def test_sync_prestashop_unauthorized(self, user_client):
        """
        Test: Sincronizzazione PrestaShop senza permessi admin
        
        Arrange: Utente senza ruolo ADMIN
        Act: POST /api/v1/sync/prestashop?store_id=1
        Assert: Status 403
        """
        store_id = 1
        
        response = user_client.post(
            f"/api/v1/sync/prestashop?store_id={store_id}"
        )
        
        # Assert
        assert_error_response(response, status_code=status.HTTP_403_FORBIDDEN)
    
    @pytest.mark.asyncio
    async def test_sync_prestashop_full(
        self,
        admin_client,
        db_session
    ):
        """
        Test: Sincronizzazione completa PrestaShop
        
        Arrange: Store esistente
        Act: POST /api/v1/sync/prestashop/full?store_id=1
        Assert: Status 202, sync_type="full"
        """
        from src.models.platform import Platform
        from src.models.store import Store

        platform = Platform(name="PrestaShop")
        db_session.add(platform)
        db_session.commit()

        store = Store(
            id_platform=platform.id_platform,
            name="Store Test",
            base_url="https://store-test.example.com",
            api_key="test-api-key",
        )
        db_session.add(store)
        db_session.commit()
        store_id = store.id_store

        with patch('src.services.ecommerce.prestashop_service.PrestaShopService') as mock_service:
            mock_instance = AsyncMock()
            mock_service.return_value.__aenter__.return_value = mock_instance
            mock_instance.sync_all_data = AsyncMock(return_value={"status": "completed"})
            
            response = admin_client.post(
                f"/api/v1/sync/prestashop/full?store_id={store_id}"
            )
            
            # Assert
            assert_success_response(response, status_code=status.HTTP_202_ACCEPTED)
            data = response.json()
            assert data["sync_type"] == "full"
