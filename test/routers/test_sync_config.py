"""
Configurazione per i test di sincronizzazione con dati limitati
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any, List


class MockPrestaShopAPI:
    """Mock dell'API PrestaShop per i test con dati limitati"""
    
    def __init__(self, max_items: int = 10):
        self.max_items = max_items
        self.responses = self._create_mock_responses()
    
    def _create_mock_responses(self) -> Dict[str, Any]:
        """Crea risposte mock con dati limitati"""
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
                        {'id': '3', 'iso_code': 'FR', 'name': 'France'},
                        {'id': '4', 'iso_code': 'DE', 'name': 'Germany'},
                        {'id': '5', 'iso_code': 'ES', 'name': 'Spain'}
                    ]
                }
            },
            'brands': {
                'manufacturers': {
                    'manufacturer': [
                        {'id': '1', 'name': 'Brand A'},
                        {'id': '2', 'name': 'Brand B'},
                        {'id': '3', 'name': 'Brand C'},
                        {'id': '4', 'name': 'Brand D'},
                        {'id': '5', 'name': 'Brand E'}
                    ]
                }
            },
            'categories': {
                'categories': {
                    'category': [
                        {'id': '1', 'name': 'Category A'},
                        {'id': '2', 'name': 'Category B'},
                        {'id': '3', 'name': 'Category C'},
                        {'id': '4', 'name': 'Category D'},
                        {'id': '5', 'name': 'Category E'}
                    ]
                }
            },
            'carriers': {
                'carriers': {
                    'carrier': [
                        {'id': '1', 'name': 'Carrier A'},
                        {'id': '2', 'name': 'Carrier B'},
                        {'id': '3', 'name': 'Carrier C'}
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
                        },
                        {
                            'id': '3',
                            'id_manufacturer': '3',
                            'id_category_default': '3',
                            'name': [{'id': '1', 'value': 'Product 3'}],
                            'reference': 'REF003',
                            'ean13': '1234567890125',
                            'weight': '1.5',
                            'depth': '12.0',
                            'height': '8.0',
                            'width': '10.0',
                            'id_default_image': '3'
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
                        },
                        {
                            'id': '3',
                            'firstname': 'Bob',
                            'lastname': 'Johnson',
                            'email': 'bob@example.com'
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
                        },
                        {
                            'id': '2',
                            'id_customer': '2',
                            'id_country': '2',
                            'firstname': 'Jane',
                            'lastname': 'Smith',
                            'address1': 'Main St 123',
                            'city': 'New York',
                            'postcode': '10001'
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
                        },
                        {
                            'id': '2',
                            'id_customer': '2',
                            'id_address_delivery': '2',
                            'id_address_invoice': '2',
                            'payment': 'Credit Card',
                            'total_paid_tax_excl': '150.00',
                            'date_add': '2024-01-02 11:00:00',
                            'associations': {
                                'order_rows': {
                                    'order_row': [
                                        {
                                            'id': '2',
                                            'product_id': '2',
                                            'product_name': 'Product 2',
                                            'product_reference': 'REF002',
                                            'product_quantity': '1',
                                            'product_price': '150.00'
                                        }
                                    ]
                                }
                            }
                        }
                    ]
                }
            }
        }
    
    def get_response(self, endpoint: str) -> Dict[str, Any]:
        """Restituisce la risposta mock per un endpoint specifico"""
        # Rimuove il prefisso '/api/' se presente
        if endpoint.startswith('/api/'):
            endpoint = endpoint[5:]
        
        # Mappa gli endpoint ai dati mock
        endpoint_mapping = {
            'languages': 'languages',
            'countries': 'countries',
            'manufacturers': 'brands',
            'categories': 'categories',
            'carriers': 'carriers',
            'products': 'products',
            'customers': 'customers',
            'addresses': 'addresses',
            'orders': 'orders'
        }
        
        key = endpoint_mapping.get(endpoint, endpoint)
        return self.responses.get(key, {})


@pytest.fixture
def mock_prestashop_api():
    """Fixture per l'API PrestaShop mock"""
    return MockPrestaShopAPI(max_items=10)


@pytest.fixture
def mock_prestashop_service_with_limited_data(mock_prestashop_api):
    """Fixture per il servizio PrestaShop con dati limitati"""
    service = AsyncMock()
    
    # Configura i metodi di sincronizzazione per restituire conteggi limitati
    service.sync_languages.return_value = [{"status": "success", "count": 2}]
    service.sync_countries.return_value = [{"status": "success", "count": 5}]
    service.sync_brands.return_value = [{"status": "success", "count": 5}]
    service.sync_categories.return_value = [{"status": "success", "count": 5}]
    service.sync_carriers.return_value = [{"status": "success", "count": 3}]
    service.sync_products.return_value = [{"status": "success", "count": 3}]
    service.sync_customers.return_value = [{"status": "success", "count": 3}]
    service.sync_addresses.return_value = [{"status": "success", "count": 2}]
    service.sync_orders.return_value = [{"status": "success", "count": 2}]
    
    # Configura la sincronizzazione completa
    service.sync_all_data.return_value = {
        'status': 'success',
        'total_processed': 10,
        'phases': [
            {'name': 'Phase 1 - Base Tables', 'processed': 5},
            {'name': 'Phase 2 - Dependent Tables', 'processed': 3},
            {'name': 'Phase 3 - Complex Tables', 'processed': 2}
        ]
    }
    
    return service


@pytest.fixture
def mock_platform_repository():
    """Fixture per il repository delle piattaforme"""
    repo = MagicMock()
    repo.get_by_id.return_value = MagicMock(
        id=1,
        name="Elettronew PrestaShop",
        api_key="QYCXMIGW3P5NL2QCILABQI6WE49K1XLR",
        base_url="https://testelettronw.com",
        is_active=True
    )
    return repo


class SyncTestData:
    """Classe per gestire i dati di test della sincronizzazione"""
    
    @staticmethod
    def get_expected_counts() -> Dict[str, int]:
        """Restituisce i conteggi attesi per ogni tipo di sincronizzazione"""
        return {
            'languages': 2,
            'countries': 5,
            'brands': 5,
            'categories': 5,
            'carriers': 3,
            'products': 3,
            'customers': 3,
            'addresses': 2,
            'orders': 2,
            'total': 10
        }
    
    @staticmethod
    def get_phase_breakdown() -> List[Dict[str, Any]]:
        """Restituisce la suddivisione per fasi"""
        return [
            {
                'name': 'Phase 1 - Base Tables',
                'items': ['languages', 'countries', 'brands', 'categories', 'carriers'],
                'expected_count': 5
            },
            {
                'name': 'Phase 2 - Dependent Tables',
                'items': ['products', 'customers', 'addresses'],
                'expected_count': 3
            },
            {
                'name': 'Phase 3 - Complex Tables',
                'items': ['orders'],
                'expected_count': 2
            }
        ]
    
    @staticmethod
    def get_incremental_counts() -> Dict[str, int]:
        """Restituisce i conteggi per la sincronizzazione incrementale"""
        return {
            'languages': 1,
            'countries': 2,
            'brands': 1,
            'categories': 1,
            'carriers': 1,
            'products': 1,
            'customers': 1,
            'addresses': 1,
            'orders': 1,
            'total': 3
        }
