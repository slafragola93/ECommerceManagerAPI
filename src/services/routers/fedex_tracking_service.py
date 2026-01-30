from typing import List, Dict, Any
import logging

from src.services.interfaces.fedex_tracking_service_interface import IFedexTrackingService
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.repository.interfaces.fedex_configuration_repository_interface import IFedexConfigurationRepository
from src.services.ecommerce.shipments.fedex_client import FedexClient
from src.services.ecommerce.shipments.fedex_mapper import FedexMapper
from src.core.exceptions import ValidationException, InfrastructureException
from src.models.fedex_configuration import FedexScopeEnum

logger = logging.getLogger(__name__)


class FedexTrackingService(IFedexTrackingService):
    """FedEx Tracking service for getting shipment tracking information"""
    
    def __init__(
        self,
        carrier_api_repository: IApiCarrierRepository,
        fedex_config_repository: IFedexConfigurationRepository,
        fedex_client: FedexClient,
        fedex_mapper: FedexMapper
    ):
        self.carrier_api_repository = carrier_api_repository
        self.fedex_config_repository = fedex_config_repository
        self.fedex_client = fedex_client
        self.fedex_mapper = fedex_mapper
    
    async def get_tracking(self, tracking_numbers: List[str], carrier_api_id: int) -> List[Dict[str, Any]]:
        """
        Get normalized tracking info for multiple shipments
        
        Args:
            tracking_numbers: List of tracking numbers to track
            carrier_api_id: Carrier API ID for authentication
            
        Returns:
            List of normalized tracking responses
        """
        try:
            # Get carrier credentials
            credentials = self.carrier_api_repository.get_auth_credentials(carrier_api_id)
            
            # Get FedEx configuration with scope TRACK
            fedex_config = self.fedex_config_repository.get_by_carrier_api_id_and_scope(carrier_api_id, FedexScopeEnum.TRACK)
            if not fedex_config:
                # Fallback: try to use SHIP scope if TRACK doesn't exist (for backward compatibility)
                logger.warning(f"FedEx configuration with scope TRACK not found for carrier_api_id {carrier_api_id}, trying SHIP scope as fallback")
                fedex_config = self.fedex_config_repository.get_by_carrier_api_id_and_scope(carrier_api_id, FedexScopeEnum.SHIP)
                if not fedex_config:
                    raise ValueError(
                        f"FedEx configuration not found for carrier_api_id {carrier_api_id} with scope TRACK or SHIP. "
                        f"Please create a FedEx configuration with scope TRACK for tracking operations."
                    )
            
            # Call FedEx API
            logger.info(f"Getting FedEx tracking for {len(tracking_numbers)} shipments")
            try:
                fedex_response = await self.fedex_client.get_tracking(tracking_numbers, credentials, fedex_config)
            except ValueError as e:
                # Handle FedEx client errors (400, 401, 403, 404, 422)
                error_str = str(e)
                logger.error(f"FedEx Client Error for tracking: {error_str}")
                
                # Check error type for more specific handling
                if "401" in error_str or "NOT.AUTHORIZED.ERROR" in error_str:
                    # Authentication/Authorization error
                    raise ValidationException(
                        f"FedEx authentication error: {error_str}",
                        details={"carrier_api_id": carrier_api_id, "error": error_str, "type": "authentication"}
                    )
                elif "403" in error_str or "FORBIDDEN.ERROR" in error_str:
                    # Forbidden - permissions issue
                    raise ValidationException(
                        f"FedEx access denied: {error_str}",
                        details={"carrier_api_id": carrier_api_id, "error": error_str, "type": "forbidden"}
                    )
                elif "404" in error_str or "NOT.FOUND.ERROR" in error_str:
                    # Resource not found
                    raise ValidationException(
                        f"FedEx resource not found: {error_str}",
                        details={"carrier_api_id": carrier_api_id, "error": error_str, "type": "not_found"}
                    )
                else:
                    # Validation errors (400, 422)
                    raise ValidationException(
                        f"FedEx validation error: {error_str}",
                        details={"carrier_api_id": carrier_api_id, "error": error_str, "type": "validation"}
                    )
            except RuntimeError as e:
                # Handle FedEx server errors (500, 503)
                error_str = str(e)
                logger.error(f"FedEx Server Error for tracking: {error_str}")
                
                # Check if it's a service unavailable error
                if "503" in error_str or "SERVICE.UNAVAILABLE.ERROR" in error_str:
                    raise InfrastructureException(
                        f"FedEx service unavailable: {error_str}",
                        details={"carrier_api_id": carrier_api_id, "error": error_str, "type": "service_unavailable"}
                    )
                else:
                    # Internal server error (500)
                    raise InfrastructureException(
                        f"FedEx server error: {error_str}",
                        details={"carrier_api_id": carrier_api_id, "error": error_str, "type": "server_error"}
                    )
            
            # Normalize response
            print(fedex_response)
            normalized_tracking = self.fedex_mapper.normalize_tracking_response(fedex_response)
            
            return normalized_tracking
            
        except (ValidationException, InfrastructureException):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            logger.error(f"Error getting FedEx tracking: {str(e)}")
            raise

