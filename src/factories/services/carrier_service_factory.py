"""
Factory for selecting the appropriate shipment and tracking service based on carrier_type
"""
from typing import Optional
from sqlalchemy.orm import Session
import logging

from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.services.interfaces.shipment_service_interface import IShipmentService
from src.services.interfaces.tracking_service_interface import ITrackingService
from src.models.carrier_api import CarrierTypeEnum
from src.core.exceptions import BusinessRuleException, NotFoundException, ErrorCode
from src.core.container_config import get_configured_container

logger = logging.getLogger(__name__)


class CarrierServiceFactory:
    """Factory for selecting carrier-specific services based on carrier_api_id"""
    
    def __init__(self, carrier_repository: IApiCarrierRepository):
        self.carrier_repository = carrier_repository
        self.container = get_configured_container()
    
    def get_shipment_service(self, id_carrier_api: int, db: Session) -> IShipmentService:
        """
        Get the appropriate shipment service based on carrier_api_id
        
        Args:
            id_carrier_api: Carrier API ID
            db: Database session
            
        Returns:
            IShipmentService implementation for the carrier type
            
        Raises:
            NotFoundException: If carrier_api not found
            BusinessRuleException: If carrier_type is not supported
        """
        # Get carrier from database
        carrier = self.carrier_repository.get_by_id(id_carrier_api)
        if not carrier:
            raise NotFoundException(
                "CarrierApi",
                id_carrier_api,
                {"id_carrier_api": id_carrier_api}
            )
        
        # Resolve service based on carrier_type
        # TODO: automatizzare in base a carriertypeenum
        if carrier.carrier_type == CarrierTypeEnum.DHL:
            from src.services.interfaces.dhl_shipment_service_interface import IDhlShipmentService
            service = self.container.resolve_with_session(IDhlShipmentService, db)
            if not isinstance(service, IShipmentService):
                raise BusinessRuleException(
                    f"DHL shipment service does not implement IShipmentService",
                    ErrorCode.DATABASE_ERROR
                )
            return service
            
        elif carrier.carrier_type == CarrierTypeEnum.BRT:
            from src.services.interfaces.brt_shipment_service_interface import IBrtShipmentService
            service = self.container.resolve_with_session(IBrtShipmentService, db)
            if not isinstance(service, IShipmentService):
                raise BusinessRuleException(
                    f"BRT shipment service does not implement IShipmentService",
                    ErrorCode.DATABASE_ERROR
                )
            return service
            
        elif carrier.carrier_type == CarrierTypeEnum.FEDEX:
            from src.services.interfaces.fedex_shipment_service_interface import IFedexShipmentService
            service = self.container.resolve_with_session(IFedexShipmentService, db)
            if not isinstance(service, IShipmentService):
                raise BusinessRuleException(
                    f"FedEx shipment service does not implement IShipmentService",
                    ErrorCode.DATABASE_ERROR
                )
            return service
        else:
            raise BusinessRuleException(
                f"Unsupported carrier type: {carrier.carrier_type}",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"carrier_type": carrier.carrier_type.value, "id_carrier_api": id_carrier_api}
            )
    
    def get_tracking_service(self, id_carrier_api: int, db: Session) -> ITrackingService:
        """
        Get the appropriate tracking service based on carrier_api_id
        
        Args:
            id_carrier_api: Carrier API ID
            db: Database session
            
        Returns:
            ITrackingService implementation for the carrier type
            
        Raises:
            NotFoundException: If carrier_api not found
            BusinessRuleException: If carrier_type is not supported
        """
        # Get carrier from database
        carrier = self.carrier_repository.get_by_id(id_carrier_api)
        if not carrier:
            raise NotFoundException(
                "CarrierApi",
                id_carrier_api,
                {"id_carrier_api": id_carrier_api}
            )
        
        # Resolve service based on carrier_type
        if carrier.carrier_type == CarrierTypeEnum.DHL:
            from src.services.interfaces.dhl_tracking_service_interface import IDhlTrackingService
            service = self.container.resolve_with_session(IDhlTrackingService, db)
            if not isinstance(service, ITrackingService):
                raise BusinessRuleException(
                    f"DHL tracking service does not implement ITrackingService",
                    ErrorCode.DATABASE_ERROR
                )
            return service
            
        elif carrier.carrier_type == CarrierTypeEnum.BRT:
            from src.services.interfaces.brt_tracking_service_interface import IBrtTrackingService
            service = self.container.resolve_with_session(IBrtTrackingService, db)
            if not isinstance(service, ITrackingService):
                raise BusinessRuleException(
                    f"BRT tracking service does not implement ITrackingService",
                    ErrorCode.DATABASE_ERROR
                )
            return service
            
        elif carrier.carrier_type == CarrierTypeEnum.FEDEX:
            from src.services.interfaces.fedex_tracking_service_interface import IFedexTrackingService
            service = self.container.resolve_with_session(IFedexTrackingService, db)
            if not isinstance(service, ITrackingService):
                raise BusinessRuleException(
                    f"FedEx tracking service does not implement ITrackingService",
                    ErrorCode.DATABASE_ERROR
                )
            return service
        else:
            raise BusinessRuleException(
                f"Unsupported carrier type: {carrier.carrier_type}",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"carrier_type": carrier.carrier_type.value, "id_carrier_api": id_carrier_api}
            )

