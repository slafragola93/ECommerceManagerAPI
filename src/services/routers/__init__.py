"""
Router Services

This module contains services that are specifically used by FastAPI routers.
These services handle business logic for API endpoints.
"""

# Import all router services for easy access
from .address_service import AddressService
from .api_carrier_service import ApiCarrierService
from .app_configuration_service import AppConfigurationService
# AuthService non esiste - auth_service.py contiene solo funzioni
from .brand_service import BrandService
from .carrier_assignment_service import CarrierAssignmentService
from .carrier_service import CarrierService
from .category_service import CategoryService
from .configuration_service import ConfigurationService
from .country_service import CountryService
from .customer_service import CustomerService
from .ddt_service import DDTService
from .fiscal_document_service import FiscalDocumentService
from .lang_service import LangService
from .message_service import MessageService
from .order_detail_service import OrderDetailService
from .order_document_service import OrderDocumentService
from .order_package_service import OrderPackageService
from .order_state_service import OrderStateService
from .payment_service import PaymentService
from .platform_service import PlatformService
from .preventivo_service import PreventivoService
from .product_service import ProductService
from .role_service import RoleService
from .sectional_service import SectionalService
from .shipping_service import ShippingService
from .shipping_state_service import ShippingStateService
from .tax_service import TaxService
from .user_service import UserService

__all__ = [
    "AddressService",
    "ApiCarrierService", 
    "AppConfigurationService",
    # "AuthService", # Non esiste - auth_service.py contiene solo funzioni
    "BrandService",
    "CarrierAssignmentService",
    "CarrierService",
    "CategoryService",
    "ConfigurationService",
    "CountryService",
    "CustomerService",
    "DDTService",
    "FiscalDocumentService",
    "LangService",
    "MessageService",
    "OrderDetailService",
    "OrderDocumentService",
    "OrderPackageService",
    # "OrderService", # Non esiste - non è stato spostato
    "OrderStateService",
    "PaymentService",
    "PlatformService",
    "PreventivoService",
    "ProductService",
    "RoleService",
    "SectionalService",
    "ShippingService",
    "ShippingStateService",
    "TaxService",
    "UserService",
]
