from typing import List, Dict, Any
import logging

from src.services.interfaces.dhl_tracking_service_interface import IDhlTrackingService
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.repository.interfaces.dhl_configuration_repository_interface import IDhlConfigurationRepository
from src.services.ecommerce.shipments.dhl_client import DhlClient

logger = logging.getLogger(__name__)


class DhlTrackingService(IDhlTrackingService):
    """DHL Tracking service for getting shipment tracking information"""
    
    def __init__(
        self,
        carrier_api_repository: IApiCarrierRepository,
        dhl_config_repository: IDhlConfigurationRepository,
        dhl_client: DhlClient
    ):
        self.carrier_api_repository = carrier_api_repository
        self.dhl_config_repository = dhl_config_repository
        self.dhl_client = dhl_client
    
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
            
            # Get DHL configuration
            dhl_config = self.dhl_config_repository.get_by_carrier_api_id(carrier_api_id)
            if not dhl_config:
                raise ValueError(f"DHL configuration not found for carrier_api_id {carrier_api_id}")
            
            # Call DHL API
            logger.info(f"Getting DHL tracking for {len(tracking_numbers)} shipments")
            dhl_response = await self.dhl_client.get_tracking_multi(tracking_numbers, credentials, dhl_config)
            
            # Normalize response
            normalized_tracking = self._normalize_tracking_response(dhl_response)
            
            return normalized_tracking
            
        except Exception as e:
            logger.error(f"Error getting DHL tracking: {str(e)}")
            raise
    
    def _normalize_tracking_response(self, dhl_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Normalize DHL tracking response to standard format
        
        Args:
            dhl_response: Raw DHL API response
            
        Returns:
            List of normalized tracking responses
        """
        normalized = []
        
        shipments = dhl_response.get("shipments", [])
        
        for shipment in shipments:
            try:
                # Extract basic info
                tracking = shipment.get("shipmentTrackingNumber", "")
                status = shipment.get("status", "Unknown")
                estimated_delivery = shipment.get("estimatedDeliveryDate")
                
                # Extract events
                events = []
                shipment_events = shipment.get("events", [])
                
                for event in shipment_events:
                    normalized_event = {
                        "date": event.get("date", ""),
                        "description": event.get("description", ""),
                        "location": self._extract_event_location(event)
                    }
                    events.append(normalized_event)
                
                # Also check piece events
                pieces = shipment.get("pieces", [])
                for piece in pieces:
                    piece_events = piece.get("events", [])
                    for event in piece_events:
                        normalized_event = {
                            "date": event.get("date", ""),
                            "description": event.get("description", ""),
                            "location": self._extract_event_location(event)
                        }
                        events.append(normalized_event)
                
                # Sort events by date
                events.sort(key=lambda x: x["date"])
                
                # Create normalized response
                normalized_shipment = {
                    "tracking_number": tracking,
                    "status": status,
                    "events": events,
                    "estimated_delivery_date": estimated_delivery
                }
                
                normalized.append(normalized_shipment)
                
            except Exception as e:
                logger.error(f"Error normalizing tracking data for shipment: {str(e)}")
                continue
        
        return normalized
    
    def _extract_event_location(self, event: Dict[str, Any]) -> str:
        """Extract location from tracking event"""
        service_area = event.get("serviceArea", [])
        if service_area and len(service_area) > 0:
            area = service_area[0]
            if isinstance(area, dict):
                return area.get("description", "")
        return ""
