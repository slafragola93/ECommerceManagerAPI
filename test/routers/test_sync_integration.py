"""
Test di integrazione per la sincronizzazione con dati reali limitati
"""

import pytest
from httpx import AsyncClient
from starlette import status
from unittest.mock import AsyncMock, patch, MagicMock
import json

from src.routers.sync import router
from src.services.ecommerce.prestashop_service import PrestaShopService
from ..utils import *
from ..test_config import *


class TestSyncIntegration:
    """Test di integrazione per la sincronizzazione con dati limitati"""

    @pytest.fixture
    def mock_prestashop_responses(self):
        """Mock delle risposte PrestaShop con dati limitati (max 10 elementi)"""
        return {
            'languages': {
                'languages': {
                    'language': [
                        {'id': '1', 'name': 'Italian', 'iso_code': 'it'},
                        {'id': '2', 'name': 'English', 'iso_code': 'en'}
                    ]
                }
            },
            'countries': {
                'countries': {
                    'country': [
                        {'id': '1', 'iso_code': 'IT', 'name': 'Italy'},
                        {'id': '2', 'iso_code': 'US', 'name': 'United States'},
                        {'id': '3', 'iso_code': 'FR', 'name': 'France'}
                    ]
                }
            },
            'brands': {
                'manufacturers': {
                    'manufacturer': [
                        {'id': '1', 'name': 'Brand A'},
                        {'id': '2', 'name': 'Brand B'},
                        {'id': '3', 'name': 'Brand C'}
                    ]
                }
            },
            'categories': {
                'categories': {
                    'category': [
                        {'id': '1', 'name': 'Category A'},
                        {'id': '2', 'name': 'Category B'},
                        {'id': '3', 'name': 'Category C'}
                    ]
                }
            },
            'carriers': {
                'carriers': {
                    'carrier': [
                        {'id': '1', 'name': 'Carrier A'},
                        {'id': '2', 'name': 'Carrier B'}
                    ]
                }
            },
            'products': {
                'products': {
                    'product': [
                        {
                            'id': '1',
                            'id_manufacturer': '1',
                            'id_category_default': '1',
                            'name': [{'id': '1', 'value': 'Product 1'}],
                            'reference': 'REF001',
                            'ean13': '1234567890123',
                            'weight': '1.0',
                            'depth': '10.0',
                            'height': '5.0',
                            'width': '8.0',
                            'id_default_image': '1'
                        },
                        {
                            'id': '2',
                            'id_manufacturer': '2',
                            'id_category_default': '2',
                            'name': [{'id': '1', 'value': 'Product 2'}],
                            'reference': 'REF002',
                            'ean13': '1234567890124',
                            'weight': '2.0',
                            'depth': '15.0',
                            'height': '10.0',
                            'width': '12.0',
                            'id_default_image': '2'
                        }
                    ]
                }
            },
            'customers': {
                'customers': {
                    'customer': [
                        {
                            'id': '1',
                            'firstname': 'John',
                            'lastname': 'Doe',
                            'email': 'john@example.com'
                        },
                        {
                            'id': '2',
                            'firstname': 'Jane',
                            'lastname': 'Smith',
                            'email': 'jane@example.com'
                        }
                    ]
                }
            },
            'addresses': {
                'addresses': {
                    'address': [
                        {
                            'id': '1',
                            'id_customer': '1',
                            'id_country': '1',
                            'firstname': 'John',
                            'lastname': 'Doe',
                            'address1': 'Via Roma 1',
                            'city': 'Milano',
                            'postcode': '20100'
                        }
                    ]
                }
            },
            'orders': {
                'orders': {
                    'order': [
                        {
                            'id': '1',
                            'id_customer': '1',
                            'id_address_delivery': '1',
                            'id_address_invoice': '1',
                            'payment': 'Bank Transfer',
                            'total_paid_tax_excl': '100.00',
                            'date_add': '2024-01-01 10:00:00',
                            'associations': {
                                'order_rows': {
                                    'order_row': [
                                        {
                                            'id': '1',
                                            'product_id': '1',
                                            'product_name': 'Product 1',
                                            'product_reference': 'REF001',
                                            'product_quantity': '2',
                                            'product_price': '50.00'
                                        }
                                    ]
                                }
                            }
                        }
                    ]
                }
            }
        }

    @pytest.mark.anyio
    async def test_full_sync_with_limited_data(self, test_user, mock_prestashop_responses):
        """Test sincronizzazione completa con dati limitati"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup platform repository mock
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock(
                id=1,
                name="Elettronew PrestaShop",
        api_key="QYCXMIGW3P5NL2QCILABQI6WE49K1XLR",
        base_url="https://testelettronw.com",
                is_active=True
            )
            mock_repo_class.return_value = mock_repo
            
            # Setup PrestaShop service mock with limited data
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

    @pytest.mark.anyio
    async def test_incremental_sync_with_limited_data(self, test_user, mock_prestashop_responses):
        """Test sincronizzazione incrementale con dati limitati"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup platform repository mock
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock(
                id=1,
                name="Elettronew PrestaShop",
        api_key="QYCXMIGW3P5NL2QCILABQI6WE49K1XLR",
        base_url="https://testelettronw.com",
                is_active=True
            )
            mock_repo_class.return_value = mock_repo
            
            # Setup PrestaShop service mock with incremental data
            mock_service = AsyncMock()
            mock_service.sync_all_data.return_value = {
                'status': 'success',
                'total_processed': 3,
                'phases': [
                    {'name': 'Phase 1 - Base Tables', 'processed': 1},
                    {'name': 'Phase 2 - Dependent Tables', 'processed': 1},
                    {'name': 'Phase 3 - Complex Tables', 'processed': 1}
                ]
            }
            mock_service_class.return_value = mock_service
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop/incremental")
            
            assert response.status_code == status.HTTP_202_ACCEPTED
            assert "Incremental synchronization started successfully" in response.json()["message"]

    @pytest.mark.anyio
    async def test_individual_sync_methods_with_limited_data(self, test_user, mock_prestashop_responses):
        """Test metodi di sincronizzazione individuali con dati limitati"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup platform repository mock
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock(
                id=1,
                name="Elettronew PrestaShop",
        api_key="QYCXMIGW3P5NL2QCILABQI6WE49K1XLR",
        base_url="https://testelettronw.com",
                is_active=True
            )
            mock_repo_class.return_value = mock_repo
            
            # Setup PrestaShop service mock
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            
            # Test each individual sync method
            sync_methods = [
                ('languages', 2),
                ('countries', 3),
                ('brands', 3),
                ('categories', 3),
                ('carriers', 2),
                ('products', 2),
                ('customers', 2),
                ('addresses', 1),
                ('orders', 1)
            ]
            
            for method_name, expected_count in sync_methods:
                # Setup mock return value for this method
                getattr(mock_service, f'sync_{method_name}').return_value = [
                    {"status": "success", "count": expected_count}
                ]
                
                async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                    response = await ac.post(f"/prestashop/{method_name}")
                
                assert response.status_code == status.HTTP_200_OK
                assert response.json()["total_processed"] == expected_count
                
                # Verify the method was called
                getattr(mock_service, f'sync_{method_name}').assert_called_once()

    @pytest.mark.anyio
    async def test_sync_with_batch_size_limit(self, test_user):
        """Test sincronizzazione con limite di batch size"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup platform repository mock
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock(
                id=1,
                name="Elettronew PrestaShop",
        api_key="QYCXMIGW3P5NL2QCILABQI6WE49K1XLR",
        base_url="https://testelettronw.com",
                is_active=True
            )
            mock_repo_class.return_value = mock_repo
            
            # Setup PrestaShop service mock
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
            
            # Verify service was initialized with correct batch_size
            mock_service_class.assert_called_once()
            call_args = mock_service_class.call_args
            assert call_args[1]['batch_size'] == 10

    @pytest.mark.anyio
    async def test_sync_with_new_elements_parameter(self, test_user):
        """Test sincronizzazione con parametro new_elements"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup platform repository mock
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock(
                id=1,
                name="Elettronew PrestaShop",
        api_key="QYCXMIGW3P5NL2QCILABQI6WE49K1XLR",
        base_url="https://testelettronw.com",
                is_active=True
            )
            mock_repo_class.return_value = mock_repo
            
            # Setup PrestaShop service mock
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
            
            # Test with new_elements=True (default)
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop")
            
            assert response.status_code == status.HTTP_202_ACCEPTED
            
            # Verify service was initialized with new_elements=True (default)
            mock_service_class.assert_called_once()
            call_args = mock_service_class.call_args
            assert call_args[1]['new_elements'] == True
            
            # Reset mock for second test
            mock_service_class.reset_mock()
            
            # Test with new_elements=False
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop/incremental?new_elements=false")
            
            assert response.status_code == status.HTTP_202_ACCEPTED
            
            # Verify service was initialized with new_elements=False
            mock_service_class.assert_called_once()
            call_args = mock_service_class.call_args
            assert call_args[1]['new_elements'] == False

    @pytest.mark.anyio
    async def test_sync_error_handling_with_limited_data(self, test_user):
        """Test gestione errori con dati limitati"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup platform repository mock
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock(
                id=1,
                name="Elettronew PrestaShop",
        api_key="QYCXMIGW3P5NL2QCILABQI6WE49K1XLR",
        base_url="https://testelettronw.com",
                is_active=True
            )
            mock_repo_class.return_value = mock_repo
            
            # Setup PrestaShop service mock to raise exception
            mock_service = AsyncMock()
            mock_service.sync_all_data.side_effect = Exception("API rate limit exceeded")
            mock_service_class.return_value = mock_service
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop")
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to start synchronization" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_individual_sync_error_handling(self, test_user):
        """Test gestione errori per sincronizzazione individuale"""
        with patch('src.routers.sync.PlatformRepository') as mock_repo_class, \
             patch('src.routers.sync.PrestaShopService') as mock_service_class:
            
            # Setup platform repository mock
            mock_repo = MagicMock()
            mock_repo.get_by_id.return_value = MagicMock(
                id=1,
                name="Elettronew PrestaShop",
        api_key="QYCXMIGW3P5NL2QCILABQI6WE49K1XLR",
        base_url="https://testelettronw.com",
                is_active=True
            )
            mock_repo_class.return_value = mock_repo
            
            # Setup PrestaShop service mock to raise exception
            mock_service = AsyncMock()
            mock_service.sync_products.side_effect = Exception("Products API unavailable")
            mock_service_class.return_value = mock_service
            
            async with AsyncClient(app=app, base_url="http://localhost:8000/api/v1/sync/") as ac:
                response = await ac.post("/prestashop/products")
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to sync products" in response.json()["detail"]
