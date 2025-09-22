"""
Test completi per la sincronizzazione con tutti i casi richiesti
"""

import pytest
from httpx import AsyncClient
from starlette import status
from unittest.mock import patch, MagicMock

from src.routers.sync import router
from ..utils import *
from ..test_config import *
from .test_sync_config import (
    mock_prestashop_api,
    mock_prestashop_service_with_limited_data,
    mock_platform_repository,
    SyncTestData
)


class TestSyncComprehensive:
    """Test completi per la sincronizzazione"""

    @pytest.mark.anyio
    async def test_full_sync_with_max_10_elements(self, test_user, mock_prestashop_service_with_limited_data, mock_platform_repository):
        """Test sincronizzazione completa con massimo 10 elementi"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mocks
            mock_repo_class.return_value = mock_platform_repository
            mock_service_class.return_value = mock_prestashop_service_with_limited_data
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop")
            
            assert response.status_code == status.HTTP_202_ACCEPTED
            assert "Synchronization started successfully" in response.json()["message"]
            
            # Verifica che il servizio sia stato inizializzato correttamente
            mock_service_class.assert_called_once()
            call_args = mock_service_class.call_args
            assert call_args[1]['new_elements'] == True  # Default value

    @pytest.mark.anyio
    async def test_incremental_sync_with_max_10_elements(self, test_user, mock_prestashop_service_with_limited_data, mock_platform_repository):
        """Test sincronizzazione incrementale con massimo 10 elementi"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mocks
            mock_repo_class.return_value = mock_platform_repository
            mock_service_class.return_value = mock_prestashop_service_with_limited_data
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop/incremental")
            
            assert response.status_code == status.HTTP_202_ACCEPTED
            assert "Incremental synchronization started successfully" in response.json()["message"]
            
            # Verifica che il servizio sia stato inizializzato con new_elements=True
            mock_service_class.assert_called_once()
            call_args = mock_service_class.call_args
            assert call_args[1]['new_elements'] == True

    @pytest.mark.anyio
    async def test_incremental_sync_with_new_elements_false(self, test_user, mock_prestashop_service_with_limited_data, mock_platform_repository):
        """Test sincronizzazione incrementale con new_elements=False"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mocks
            mock_repo_class.return_value = mock_platform_repository
            mock_service_class.return_value = mock_prestashop_service_with_limited_data
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop/incremental?new_elements=false")
            
            assert response.status_code == status.HTTP_202_ACCEPTED
            assert "Incremental synchronization started successfully" in response.json()["message"]
            
            # Verifica che il servizio sia stato inizializzato con new_elements=False
            mock_service_class.assert_called_once()
            call_args = mock_service_class.call_args
            assert call_args[1]['new_elements'] == False

    @pytest.mark.anyio
    async def test_individual_sync_methods_with_limited_data(self, test_user, mock_prestashop_service_with_limited_data, mock_platform_repository):
        """Test tutti i metodi di sincronizzazione individuali con dati limitati"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mocks
            mock_repo_class.return_value = mock_platform_repository
            mock_service_class.return_value = mock_prestashop_service_with_limited_data
            
            # Test data
            expected_counts = SyncTestData.get_expected_counts()
            sync_methods = [
                'languages', 'countries', 'brands', 'categories', 'carriers',
                'products', 'customers', 'addresses', 'orders'
            ]
            
            for method in sync_methods:
                # Reset mock per ogni test
                mock_service_class.reset_mock()
                
                async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                    response = await ac.post(f"/prestashop/{method}")
                
                assert response.status_code == status.HTTP_200_OK
                assert response.json()["total_processed"] == expected_counts[method]
                
                # Verifica che il metodo corretto sia stato chiamato
                getattr(mock_prestashop_service_with_limited_data, f'sync_{method}').assert_called_once()

    @pytest.mark.anyio
    async def test_sync_with_batch_size_10(self, test_user, mock_prestashop_service_with_limited_data, mock_platform_repository):
        """Test sincronizzazione con batch_size=10"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mocks
            mock_repo_class.return_value = mock_platform_repository
            mock_service_class.return_value = mock_prestashop_service_with_limited_data
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop?batch_size=10")
            
            assert response.status_code == status.HTTP_202_ACCEPTED
            
            # Verifica che il servizio sia stato inizializzato con batch_size=10
            mock_service_class.assert_called_once()
            call_args = mock_service_class.call_args
            assert call_args[1]['batch_size'] == 10

    @pytest.mark.anyio
    async def test_individual_sync_with_batch_size_10(self, test_user, mock_prestashop_service_with_limited_data, mock_platform_repository):
        """Test sincronizzazione individuale con batch_size=10"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mocks
            mock_repo_class.return_value = mock_platform_repository
            mock_service_class.return_value = mock_prestashop_service_with_limited_data
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop/products?batch_size=10")
            
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["total_processed"] == 3  # Expected count for products
            
            # Verifica che il servizio sia stato inizializzato con batch_size=10
            mock_service_class.assert_called_once()
            call_args = mock_service_class.call_args
            assert call_args[1]['batch_size'] == 10

    @pytest.mark.anyio
    async def test_sync_phase_breakdown(self, test_user, mock_prestashop_service_with_limited_data, mock_platform_repository):
        """Test che verifica la suddivisione per fasi della sincronizzazione"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mocks
            mock_repo_class.return_value = mock_platform_repository
            mock_service_class.return_value = mock_prestashop_service_with_limited_data
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop")
            
            assert response.status_code == status.HTTP_202_ACCEPTED
            
            # Verifica che il servizio sia stato chiamato
            mock_prestashop_service_with_limited_data.sync_all_data.assert_called_once()
            
            # Verifica la struttura della risposta del servizio
            sync_result = mock_prestashop_service_with_limited_data.sync_all_data.return_value
            assert sync_result['status'] == 'success'
            assert sync_result['total_processed'] == 10
            assert len(sync_result['phases']) == 3
            
            # Verifica le fasi
            phase_breakdown = SyncTestData.get_phase_breakdown()
            for i, phase in enumerate(sync_result['phases']):
                expected_phase = phase_breakdown[i]
                assert phase['name'] == expected_phase['name']
                assert phase['processed'] == expected_phase['expected_count']

    @pytest.mark.anyio
    async def test_sync_error_scenarios(self, test_user, mock_platform_repository):
        """Test scenari di errore nella sincronizzazione"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mocks
            mock_repo_class.return_value = mock_platform_repository
            
            # Test 1: Piattaforma non trovata
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = None
            mock_repo_class.return_value = mock_repo
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop")
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "PrestaShop platform not found" in response.json()["detail"]
            
            # Test 2: Piattaforma inattiva
            mock_repo.get_by_id.return_value = MagicMock(
                id=1,
                name="Elettronew PrestaShop",
                is_active=False
            )
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop")
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "PrestaShop platform is not active" in response.json()["detail"]
            
            # Test 3: Errore del servizio
            mock_repo.get_by_id.return_value = MagicMock(
                id=1,
                name="Elettronew PrestaShop",
        api_key="QYCXMIGW3P5NL2QCILABQI6WE49K1XLR",
        base_url="https://testelettronw.com",
                is_active=True
            )
            
            mock_service = AsyncMock()
            mock_service.sync_all_data.side_effect = Exception("API connection failed")
            mock_service_class.return_value = mock_service
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop")
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to start synchronization" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_sync_authentication_requirements(self):
        """Test requisiti di autenticazione per la sincronizzazione"""
        # Test senza autenticazione
        async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
            response = await ac.post("/prestashop")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.anyio
    async def test_sync_with_different_parameters(self, test_user, mock_prestashop_service_with_limited_data, mock_platform_repository):
        """Test sincronizzazione con diversi parametri"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mocks
            mock_repo_class.return_value = mock_platform_repository
            mock_service_class.return_value = mock_prestashop_service_with_limited_data
            
            # Test con parametri combinati
            test_cases = [
                ("/prestashop?batch_size=5&new_elements=true", {'batch_size': 5, 'new_elements': True}),
                ("/prestashop?batch_size=20&new_elements=false", {'batch_size': 20, 'new_elements': False}),
                ("/prestashop/incremental?new_elements=true", {'new_elements': True}),
                ("/prestashop/incremental?new_elements=false", {'new_elements': False}),
            ]
            
            for endpoint, expected_params in test_cases:
                # Reset mock per ogni test
                mock_service_class.reset_mock()
                
                async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                    response = await ac.post(endpoint)
                
                assert response.status_code == status.HTTP_202_ACCEPTED
                
                # Verifica parametri
                mock_service_class.assert_called_once()
                call_args = mock_service_class.call_args
                for param, expected_value in expected_params.items():
                    assert call_args[1][param] == expected_value

    @pytest.mark.anyio
    async def test_sync_performance_with_limited_data(self, test_user, mock_prestashop_service_with_limited_data, mock_platform_repository):
        """Test performance della sincronizzazione con dati limitati"""
        import time
        
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mocks
            mock_repo_class.return_value = mock_platform_repository
            mock_service_class.return_value = mock_prestashop_service_with_limited_data
            
            start_time = time.time()
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop")
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            assert response.status_code == status.HTTP_202_ACCEPTED
            # Verifica che la risposta sia stata veloce (meno di 1 secondo per i test)
            assert execution_time < 1.0
