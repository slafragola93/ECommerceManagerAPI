"""
Configurazione del container di dependency injection
"""
from src.core.container import container
from src.repository.interfaces.customer_repository_interface import ICustomerRepository
from src.repository.customer_repository import CustomerRepository
from src.services.interfaces.customer_service_interface import ICustomerService
from src.services.routers.customer_service import CustomerService
from src.repository.interfaces.user_repository_interface import IUserRepository
from src.repository.user_repository import UserRepository
from src.services.interfaces.user_service_interface import IUserService
from src.services.routers.user_service import UserService
from src.repository.interfaces.role_repository_interface import IRoleRepository
from src.repository.role_repository import RoleRepository
from src.services.interfaces.role_service_interface import IRoleService
from src.services.routers.role_service import RoleService
from src.repository.interfaces.configuration_repository_interface import IConfigurationRepository
from src.repository.configuration_repository import ConfigurationRepository
from src.services.interfaces.configuration_service_interface import IConfigurationService
from src.services.routers.configuration_service import ConfigurationService
from src.repository.interfaces.app_configuration_repository_interface import IAppConfigurationRepository
from src.repository.app_configuration_repository import AppConfigurationRepository
from src.services.interfaces.app_configuration_service_interface import IAppConfigurationService
from src.services.routers.app_configuration_service import AppConfigurationService
from src.repository.interfaces.lang_repository_interface import ILangRepository
from src.repository.lang_repository import LangRepository
from src.services.interfaces.lang_service_interface import ILangService
from src.services.routers.lang_service import LangService
from src.repository.interfaces.category_repository_interface import ICategoryRepository
from src.repository.category_repository import CategoryRepository
from src.services.interfaces.category_service_interface import ICategoryService
from src.services.routers.category_service import CategoryService
from src.repository.interfaces.brand_repository_interface import IBrandRepository
from src.repository.brand_repository import BrandRepository
from src.services.interfaces.brand_service_interface import IBrandService
from src.services.routers.brand_service import BrandService
from src.repository.interfaces.product_repository_interface import IProductRepository
from src.repository.product_repository import ProductRepository
from src.services.interfaces.product_service_interface import IProductService
from src.services.routers.product_service import ProductService
from src.repository.interfaces.shipping_state_repository_interface import IShippingStateRepository
from src.repository.shipping_state_repository import ShippingStateRepository
from src.services.interfaces.shipping_state_service_interface import IShippingStateService
from src.services.routers.shipping_state_service import ShippingStateService
from src.repository.interfaces.country_repository_interface import ICountryRepository
from src.repository.country_repository import CountryRepository
from src.services.interfaces.country_service_interface import ICountryService
from src.services.routers.country_service import CountryService
from src.repository.interfaces.address_repository_interface import IAddressRepository
from src.repository.address_repository import AddressRepository
from src.services.interfaces.address_service_interface import IAddressService
from src.services.routers.address_service import AddressService
from src.repository.interfaces.carrier_repository_interface import ICarrierRepository
from src.repository.carrier_repository import CarrierRepository
from src.services.interfaces.carrier_service_interface import ICarrierService
from src.services.routers.carrier_service import CarrierService
from src.repository.interfaces.platform_repository_interface import IPlatformRepository
from src.repository.platform_repository import PlatformRepository
from src.services.interfaces.platform_service_interface import IPlatformService
from src.services.routers.platform_service import PlatformService
from src.repository.interfaces.sectional_repository_interface import ISectionalRepository
from src.repository.sectional_repository import SectionalRepository
from src.services.interfaces.sectional_service_interface import ISectionalService
from src.services.routers.sectional_service import SectionalService
from src.repository.interfaces.message_repository_interface import IMessageRepository
from src.repository.message_repository import MessageRepository
from src.services.interfaces.message_service_interface import IMessageService
from src.services.routers.message_service import MessageService
from src.repository.interfaces.payment_repository_interface import IPaymentRepository
from src.repository.payment_repository import PaymentRepository
from src.services.interfaces.payment_service_interface import IPaymentService
from src.services.routers.payment_service import PaymentService
from src.repository.interfaces.tax_repository_interface import ITaxRepository
from src.repository.tax_repository import TaxRepository
from src.services.interfaces.tax_service_interface import ITaxService
from src.services.routers.tax_service import TaxService
from src.repository.interfaces.order_state_repository_interface import IOrderStateRepository
from src.repository.order_state_repository import OrderStateRepository
from src.services.interfaces.order_state_service_interface import IOrderStateService
from src.services.routers.order_state_service import OrderStateService
from src.repository.interfaces.shipping_repository_interface import IShippingRepository
from src.repository.shipping_repository import ShippingRepository
from src.services.interfaces.shipping_service_interface import IShippingService
from src.services.routers.shipping_service import ShippingService
from src.repository.interfaces.order_package_repository_interface import IOrderPackageRepository
from src.repository.order_package_repository import OrderPackageRepository
from src.services.interfaces.order_package_service_interface import IOrderPackageService
from src.services.routers.order_package_service import OrderPackageService
from src.repository.interfaces.order_repository_interface import IOrderRepository
from src.repository.order_repository import OrderRepository

def configure_container():
    """Configura il container di dependency injection"""
    
    # Repository - Transient (nuova istanza per ogni richiesta)
    container.register_transient(ICustomerRepository, CustomerRepository)
    container.register_transient(IUserRepository, UserRepository)
    container.register_transient(IRoleRepository, RoleRepository)
    container.register_transient(IConfigurationRepository, ConfigurationRepository)
    container.register_transient(IAppConfigurationRepository, AppConfigurationRepository)
    container.register_transient(ILangRepository, LangRepository)
    container.register_transient(ICategoryRepository, CategoryRepository)
    container.register_transient(IBrandRepository, BrandRepository)
    container.register_transient(IProductRepository, ProductRepository)
    container.register_transient(IShippingStateRepository, ShippingStateRepository)
    container.register_transient(ICountryRepository, CountryRepository)
    container.register_transient(IAddressRepository, AddressRepository)
    container.register_transient(ICarrierRepository, CarrierRepository)
    container.register_transient(IPlatformRepository, PlatformRepository)
    container.register_transient(ISectionalRepository, SectionalRepository)
    container.register_transient(IMessageRepository, MessageRepository)
    container.register_transient(IPaymentRepository, PaymentRepository)
    container.register_transient(ITaxRepository, TaxRepository)
    container.register_transient(IOrderStateRepository, OrderStateRepository)
    container.register_transient(IShippingRepository, ShippingRepository)
    container.register_transient(IOrderPackageRepository, OrderPackageRepository)
    container.register_transient(IOrderRepository, OrderRepository)
    
    # Registra API Carrier
    from src.services.interfaces.api_carrier_service_interface import IApiCarrierService
    from src.services.routers.api_carrier_service import ApiCarrierService
    from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
    from src.repository.api_carrier_repository import ApiCarrierRepository
    
    container.register_transient(IApiCarrierRepository, ApiCarrierRepository)
    
    # Registra Carrier Assignment
    from src.services.interfaces.carrier_assignment_service_interface import ICarrierAssignmentService
    from src.services.routers.carrier_assignment_service import CarrierAssignmentService
    from src.repository.interfaces.carrier_assignment_repository_interface import ICarrierAssignmentRepository
    from src.repository.carrier_assignment_repository import CarrierAssignmentRepository
    
    container.register_transient(ICarrierAssignmentRepository, CarrierAssignmentRepository)
    
    # Registra Order Detail
    from src.services.interfaces.order_detail_service_interface import IOrderDetailService
    from src.services.routers.order_detail_service import OrderDetailService
    from src.repository.interfaces.order_detail_repository_interface import IOrderDetailRepository
    from src.repository.order_detail_repository import OrderDetailRepository
    
    container.register_transient(IOrderDetailRepository, OrderDetailRepository)
    
    # Registra Fiscal Document
    from src.services.interfaces.fiscal_document_service_interface import IFiscalDocumentService
    from src.services.routers.fiscal_document_service import FiscalDocumentService
    from src.repository.interfaces.fiscal_document_repository_interface import IFiscalDocumentRepository
    from src.repository.fiscal_document_repository import FiscalDocumentRepository
    
    container.register_transient(IFiscalDocumentRepository, FiscalDocumentRepository)
    
    # Services - Transient (nuova istanza per ogni richiesta)
    container.register_transient(ICustomerService, CustomerService)
    container.register_transient(IUserService, UserService)
    container.register_transient(IRoleService, RoleService)
    container.register_transient(IConfigurationService, ConfigurationService)
    container.register_transient(IAppConfigurationService, AppConfigurationService)
    container.register_transient(ILangService, LangService)
    container.register_transient(ICategoryService, CategoryService)
    container.register_transient(IBrandService, BrandService)
    container.register_transient(IProductService, ProductService)
    container.register_transient(IShippingStateService, ShippingStateService)
    container.register_transient(ICountryService, CountryService)
    container.register_transient(IAddressService, AddressService)
    container.register_transient(ICarrierService, CarrierService)
    container.register_transient(IPlatformService, PlatformService)
    container.register_transient(ISectionalService, SectionalService)
    container.register_transient(IMessageService, MessageService)
    container.register_transient(IPaymentService, PaymentService)
    container.register_transient(ITaxService, TaxService)
    container.register_transient(IOrderStateService, OrderStateService)
    container.register_transient(IShippingService, ShippingService)
    container.register_transient(IOrderPackageService, OrderPackageService)
    container.register_transient(IApiCarrierService, ApiCarrierService)
    container.register_transient(ICarrierAssignmentService, CarrierAssignmentService)
    container.register_transient(IOrderDetailService, OrderDetailService)
    container.register_transient(IFiscalDocumentService, FiscalDocumentService)
    
    # BRT Configuration
    from src.repository.interfaces.brt_configuration_repository_interface import IBrtConfigurationRepository
    from src.repository.brt_configuration_repository import BrtConfigurationRepository
    from src.services.interfaces.brt_configuration_service_interface import IBrtConfigurationService
    from src.services.routers.brt_configuration_service import BrtConfigurationService
    
    container.register_transient(IBrtConfigurationRepository, BrtConfigurationRepository)
    container.register_transient(IBrtConfigurationService, BrtConfigurationService)
    
    # Fedex Configuration
    from src.repository.interfaces.fedex_configuration_repository_interface import IFedexConfigurationRepository
    from src.repository.fedex_configuration_repository import FedexConfigurationRepository
    from src.services.interfaces.fedex_configuration_service_interface import IFedexConfigurationService
    from src.services.routers.fedex_configuration_service import FedexConfigurationService
    
    container.register_transient(IFedexConfigurationRepository, FedexConfigurationRepository)
    container.register_transient(IFedexConfigurationService, FedexConfigurationService)
    
    # DHL Configuration
    from src.repository.interfaces.dhl_configuration_repository_interface import IDhlConfigurationRepository
    from src.repository.dhl_configuration_repository import DhlConfigurationRepository
    from src.services.interfaces.dhl_configuration_service_interface import IDhlConfigurationService
    from src.services.routers.dhl_configuration_service import DhlConfigurationService
    
    container.register_transient(IDhlConfigurationRepository, DhlConfigurationRepository)
    container.register_transient(IDhlConfigurationService, DhlConfigurationService)
    
    # DHL Shipment Services
    from src.repository.interfaces.shipment_document_repository_interface import IShipmentDocumentRepository
    from src.repository.shipment_document_repository import ShipmentDocumentRepository
    from src.services.interfaces.dhl_shipment_service_interface import IDhlShipmentService
    from src.services.routers.dhl_shipment_service import DhlShipmentService
    from src.services.interfaces.dhl_tracking_service_interface import IDhlTrackingService
    from src.services.routers.dhl_tracking_service import DhlTrackingService
    from src.services.ecommerce.shipments.dhl_client import DhlClient
    from src.services.ecommerce.shipments.dhl_mapper import DhlMapper
    
    # Register DHL repositories
    container.register_transient(IShipmentDocumentRepository, ShipmentDocumentRepository)
    
    # Register DHL services (singleton for client, transient for others)
    container.register_singleton(DhlClient, DhlClient)
    container.register_transient(DhlMapper, DhlMapper)
    container.register_transient(IDhlShipmentService, DhlShipmentService)
    container.register_transient(IDhlTrackingService, DhlTrackingService)
    

def get_configured_container():
    """Ottiene il container configurato"""
    if not container.is_registered(ICustomerRepository):
        configure_container()
    return container
