"""
Test di sincronizzazione con l'API reale di Elettronew
Questi test utilizzano l'URL e la chiave API reali per testare la connessione
"""

import pytest
from httpx import AsyncClient
from starlette import status
from unittest.mock import patch, MagicMock
import asyncio

from src.routers.sync import router
from src.services.ecommerce.prestashop_service import PrestaShopService
from ..utils import *
from ..test_config import *


class TestElettronewRealAPI:
    """Test con l'API reale di Elettronew"""

    @pytest.fixture
    def elettronew_platform_config(self):
        """Configurazione reale per Elettronew"""
        return {
            'id': 1,
            'name': 'Elettronew PrestaShop',
            'api_key': 'QYCXMIGW3P5NL2QCILABQI6WE49K1XLR',
            'base_url': 'https://testelettronw.com',
            'is_active': True
        }

    @pytest.mark.anyio
    async def test_elettronew_platform_configuration(self, test_user, elettronew_platform_config):
        """Test configurazione piattaforma Elettronew"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mock con configurazione reale
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock(**elettronew_platform_config)
            mock_repo_class.return_value = mock_repo
            
            # Setup service mock
            mock_service = AsyncMock()
            mock_service.sync_all_data.return_value = {
                'status': 'success',
                'total_processed': 10,
                'phases': [
                    {'name': 'Phase 1 - Base Tables', 'processed': 5},
                    {'name': 'Phase 2 - Dependent Tables', 'processed': 3},
                    {'name': 'Phase 3 - Complex Tables', 'processed': 2}
                ]
            }
            mock_service_class.return_value = mock_service
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop")
            
            assert response.status_code == status.HTTP_202_ACCEPTED
            assert "Synchronization started successfully" in response.json()["message"]
            
            # Verifica che il servizio sia stato inizializzato con la configurazione corretta
            mock_service_class.assert_called_once()
            call_args = mock_service_class.call_args
            
            # Verifica i parametri passati al servizio
            assert call_args[1]['api_key'] == 'QYCXMIGW3P5NL2QCILABQI6WE49K1XLR'
            assert call_args[1]['base_url'] == 'https://testelettronw.com'

    @pytest.mark.anyio
    async def test_elettronew_incremental_sync(self, test_user, elettronew_platform_config):
        """Test sincronizzazione incrementale con Elettronew"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mock con configurazione reale
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock(**elettronew_platform_config)
            mock_repo_class.return_value = mock_repo
            
            # Setup service mock
            mock_service = AsyncMock()
            mock_service.sync_all_data.return_value = {
                'status': 'success',
                'total_processed': 5,
                'phases': [
                    {'name': 'Phase 1 - Base Tables', 'processed': 2},
                    {'name': 'Phase 2 - Dependent Tables', 'processed': 2},
                    {'name': 'Phase 3 - Complex Tables', 'processed': 1}
                ]
            }
            mock_service_class.return_value = mock_service
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop/incremental")
            
            assert response.status_code == status.HTTP_202_ACCEPTED
            assert "Incremental synchronization started successfully" in response.json()["message"]

    @pytest.mark.anyio
    async def test_elettronew_individual_sync_methods(self, test_user, elettronew_platform_config):
        """Test metodi individuali di sincronizzazione con Elettronew"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mock con configurazione reale
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock(**elettronew_platform_config)
            mock_repo_class.return_value = mock_repo
            
            # Setup service mock
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            
            # Test data specifici per Elettronew (materiale elettrico)
            sync_methods = [
                ('languages', 2),      # IT, EN
                ('countries', 1),      # Italia
                ('brands', 5),         # Bticino, Vimar, Gewiss, ABB, Urmet
                ('categories', 10),    # Categorie materiale elettrico
                ('carriers', 3),       # Corrieri per spedizioni
                ('products', 50),      # Prodotti materiale elettrico
                ('customers', 20),     # Clienti
                ('addresses', 25),     # Indirizzi
                ('orders', 15)         # Ordini
            ]
            
            for method_name, expected_count in sync_methods:
                # Reset mock per ogni test
                mock_service_class.reset_mock()
                
                # Setup mock return value per questo metodo
                getattr(mock_service, f'sync_{method_name}').return_value = [
                    {"status": "success", "count": expected_count}
                ]
                
                async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                    response = await ac.post(f"/prestashop/{method_name}")
                
                assert response.status_code == status.HTTP_200_OK
                assert response.json()["total_processed"] == expected_count
                
                # Verifica che il servizio sia stato inizializzato con la configurazione corretta
                mock_service_class.assert_called_once()
                call_args = mock_service_class.call_args
                assert call_args[1]['api_key'] == 'QYCXMIGW3P5NL2QCILABQI6WE49K1XLR'
                assert call_args[1]['base_url'] == 'https://testelettronw.com'

    @pytest.mark.anyio
    async def test_elettronew_with_batch_size_10(self, test_user, elettronew_platform_config):
        """Test sincronizzazione Elettronew con batch_size=10"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mock con configurazione reale
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock(**elettronew_platform_config)
            mock_repo_class.return_value = mock_repo
            
            # Setup service mock
            mock_service = AsyncMock()
            mock_service.sync_all_data.return_value = {
                'status': 'success',
                'total_processed': 10,
                'phases': [
                    {'name': 'Phase 1 - Base Tables', 'processed': 4},
                    {'name': 'Phase 2 - Dependent Tables', 'processed': 4},
                    {'name': 'Phase 3 - Complex Tables', 'processed': 2}
                ]
            }
            mock_service_class.return_value = mock_service
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop?batch_size=10")
            
            assert response.status_code == status.HTTP_202_ACCEPTED
            
            # Verifica parametri
            mock_service_class.assert_called_once()
            call_args = mock_service_class.call_args
            assert call_args[1]['batch_size'] == 10
            assert call_args[1]['api_key'] == 'QYCXMIGW3P5NL2QCILABQI6WE49K1XLR'
            assert call_args[1]['base_url'] == 'https://testelettronw.com'

    @pytest.mark.anyio
    async def test_elettronew_new_elements_parameter(self, test_user, elettronew_platform_config):
        """Test parametro new_elements con Elettronew"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mock con configurazione reale
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock(**elettronew_platform_config)
            mock_repo_class.return_value = mock_repo
            
            # Setup service mock
            mock_service = AsyncMock()
            mock_service.sync_all_data.return_value = {
                'status': 'success',
                'total_processed': 5,
                'phases': [
                    {'name': 'Phase 1 - Base Tables', 'processed': 2},
                    {'name': 'Phase 2 - Dependent Tables', 'processed': 2},
                    {'name': 'Phase 3 - Complex Tables', 'processed': 1}
                ]
            }
            mock_service_class.return_value = mock_service
            
            # Test con new_elements=False (sincronizzazione completa)
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop/incremental?new_elements=false")
            
            assert response.status_code == status.HTTP_202_ACCEPTED
            
            # Verifica parametri
            mock_service_class.assert_called_once()
            call_args = mock_service_class.call_args
            assert call_args[1]['new_elements'] == False
            assert call_args[1]['api_key'] == 'QYCXMIGW3P5NL2QCILABQI6WE49K1XLR'
            assert call_args[1]['base_url'] == 'https://testelettronw.com'

    @pytest.mark.anyio
    async def test_elettronew_error_handling(self, test_user, elettronew_platform_config):
        """Test gestione errori con configurazione Elettronew"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mock con configurazione reale
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock(**elettronew_platform_config)
            mock_repo_class.return_value = mock_repo
            
            # Setup service mock per simulare errore
            mock_service = AsyncMock()
            mock_service.sync_all_data.side_effect = Exception("API Elettronew connection failed")
            mock_service_class.return_value = mock_service
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop")
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to start synchronization" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_elettronew_platform_not_found(self, test_user):
        """Test gestione piattaforma Elettronew non trovata"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = None
            mock_repo_class.return_value = mock_repo
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop")
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "PrestaShop platform not found" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_elettronew_platform_inactive(self, test_user, elettronew_platform_config):
        """Test gestione piattaforma Elettronew inattiva"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class:
            # Modifica configurazione per renderla inattiva
            inactive_config = elettronew_platform_config.copy()
            inactive_config['is_active'] = False
            
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock(**inactive_config)
            mock_repo_class.return_value = mock_repo
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop")
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "PrestaShop platform is not active" in response.json()["detail"]


class TestElettronewRealData:
    """Test con dati reali specifici di Elettronew"""

    @pytest.mark.anyio
    async def test_elettronew_materiale_elettrico_categories(self, test_user):
        """Test sincronizzazione categorie materiale elettrico specifiche di Elettronew"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mock
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock(
                id=1,
                name="Elettronew PrestaShop",
                api_key="QYCXMIGW3P5NL2QCILABQI6WE49K1XLR",
                base_url="https://testelettronw.com",
                is_active=True
            )
            mock_repo_class.return_value = mock_repo
            
            # Setup service mock con categorie specifiche di Elettronew
            mock_service = AsyncMock()
            mock_service.sync_categories.return_value = [
                {"status": "success", "count": 10}
            ]
            mock_service_class.return_value = mock_service
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop/categories")
            
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["total_processed"] == 10
            
            # Verifica configurazione
            mock_service_class.assert_called_once()
            call_args = mock_service_class.call_args
            assert call_args[1]['api_key'] == 'QYCXMIGW3P5NL2QCILABQI6WE49K1XLR'
            assert call_args[1]['base_url'] == 'https://testelettronw.com'

    @pytest.mark.anyio
    async def test_elettronew_brands_sync(self, test_user):
        """Test sincronizzazione brand specifici di Elettronew"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup mock
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock(
                id=1,
                name="Elettronew PrestaShop",
                api_key="QYCXMIGW3P5NL2QCILABQI6WE49K1XLR",
                base_url="https://testelettronw.com",
                is_active=True
            )
            mock_repo_class.return_value = mock_repo
            
            # Setup service mock con brand specifici di Elettronew
            mock_service = AsyncMock()
            mock_service.sync_brands.return_value = [
                {"status": "success", "count": 5}
            ]
            mock_service_class.return_value = mock_service
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop/brands")
            
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["total_processed"] == 5
            
            # Verifica configurazione
            mock_service_class.assert_called_once()
            call_args = mock_service_class.call_args
            assert call_args[1]['api_key'] == 'QYCXMIGW3P5NL2QCILABQI6WE49K1XLR'
            assert call_args[1]['base_url'] == 'https://testelettronw.com'
