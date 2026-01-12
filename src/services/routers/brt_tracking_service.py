from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from src.core.exceptions import NotFoundException
from src.services.interfaces.brt_tracking_service_interface import IBrtTrackingService
from src.repository.interfaces.api_carrier_repository_interface import IApiCarrierRepository
from src.repository.interfaces.brt_configuration_repository_interface import IBrtConfigurationRepository
from src.services.ecommerce.shipments.brt_client import BrtClient

logger = logging.getLogger(__name__)


class BrtTrackingService(IBrtTrackingService):
    """BRT Tracking service for getting shipment tracking information"""
    
    def __init__(
        self,
        carrier_api_repository: IApiCarrierRepository,
        brt_config_repository: IBrtConfigurationRepository,
        brt_client: BrtClient
    ):
        self.carrier_api_repository = carrier_api_repository
        self.brt_config_repository = brt_config_repository
        self.brt_client = brt_client
    
    async def get_tracking(self, tracking_numbers: List[str], carrier_api_id: int) -> List[Dict[str, Any]]:
        """
        Get normalized tracking info for multiple shipments
        
        Args:
            tracking_numbers: List of tracking numbers (parcel IDs) to track
            carrier_api_id: Carrier API ID for authentication
            
        Returns:
            List of normalized tracking responses
        """
        # Get carrier credentials (for consistency, but BRT uses brt_config)
        credentials = self.carrier_api_repository.get_auth_credentials(carrier_api_id)
        
        # Get BRT configuration
        brt_config = self.brt_config_repository.get_by_carrier_api_id(carrier_api_id)
        if not brt_config:
            raise NotFoundException("BrtConfiguration", carrier_api_id, {"carrier_api_id": carrier_api_id})
        
        # Verifica che le credenziali siano presenti per il tracking
        if not hasattr(brt_config, 'api_user') or not brt_config.api_user:
            raise ValueError(f"BRT api_user is missing or empty in BrtConfiguration for carrier_api_id {carrier_api_id}")
        if not hasattr(brt_config, 'api_password') or not brt_config.api_password:
            raise ValueError(f"BRT api_password is missing or empty in BrtConfiguration for carrier_api_id {carrier_api_id}")
        
        # BRT tracking API only supports single parcel ID per request
        # So we need to make multiple requests
        
        normalized_tracking = []
        for tracking_number in tracking_numbers:
            # Call BRT API for single parcel
            brt_response = await self.brt_client.get_tracking(
                parcel_id=tracking_number,
                credentials=credentials,
                brt_config=brt_config
            )
            
            # Normalize response
            normalized = self._normalize_tracking_response(brt_response, tracking_number)
            if normalized:
                normalized_tracking.append(normalized)
        
        return normalized_tracking
    
    def _normalize_tracking_response(self, brt_response: Dict[str, Any], tracking_number: str) -> Optional[Dict[str, Any]]:
        """
        Normalize BRT tracking response to standard format
        
        Args:
            brt_response: Raw BRT API response
            tracking_number: Original tracking number used in request
            
        Returns:
            Normalized tracking response or None if error
        """
        # Lazy import to avoid circulars
        from src.services.ecommerce.shipments.brt_status_mapping import (
            map_brt_description_to_internal_state_id,
            DEFAULT_STATE_ID,
        )
        
        try:
            # BRT response structure: ttParcelIdResponse.lista_eventi[].evento
            root = brt_response.get("ttParcelIdResponse", {})
            event_list = root.get("lista_eventi", [])
            
            # Extract events
            events: List[Dict[str, Any]] = []
            for event_wrapper in event_list:
                evento = event_wrapper.get("evento", {})
                if not evento:
                    continue
                
                # Extract event data
                descrizione = evento.get("descrizione", "")
                data = evento.get("data", "")
                ora = evento.get("ora", "")
                filiale = evento.get("filiale", "")
                
                # Combine date and time
                event_date = ""
                if data:
                    if ora:
                        event_date = f"{data} {ora}".strip()
                    else:
                        event_date = data
                
                # Map description to internal state
                internal_state_id = map_brt_description_to_internal_state_id(descrizione)
                
                normalized_event = {
                    "date": event_date,
                    "description": descrizione,
                    "location": filiale,
                    "code": None,  # BRT doesn't use codes
                    "internal_state_id": internal_state_id,
                }
                events.append(normalized_event)
            
            # Sort events by date (most recent first, then reverse to get chronological)
            # BRT events are usually in reverse chronological order
            events.sort(key=lambda x: x["date"] or "", reverse=True)
            events.reverse()  # Now chronological (oldest first)
            
            # Derive current internal state from last event (if any)
            current_internal_state_id = (
                events[-1]["internal_state_id"] if events else DEFAULT_STATE_ID
            )
            
            # Determine status from last event description
            status = "Unknown"
            if events:
                last_event_desc = events[-1].get("description", "")
                if "consegnato" in last_event_desc.lower() or "consegnata" in last_event_desc.lower():
                    status = "Delivered"
                elif "in transito" in last_event_desc.lower() or "in viaggio" in last_event_desc.lower():
                    status = "In Transit"
                elif "presa in carico" in last_event_desc.lower() or "accettato" in last_event_desc.lower():
                    status = "Accepted"
                elif "in consegna" in last_event_desc.lower():
                    status = "Out for Delivery"
                elif "bloccato" in last_event_desc.lower() or "ritardato" in last_event_desc.lower():
                    status = "Delayed"
                elif "annullato" in last_event_desc.lower() or "cancellato" in last_event_desc.lower():
                    status = "Cancelled"
            
            # Format events for NormalizedTrackingEventSchema (only date, description, location)
            normalized_events = []
            for event in events:
                normalized_events.append({
                    "date": event.get("date", ""),
                    "description": event.get("description", ""),
                    "location": event.get("location")
                })
            
            # Create normalized response
            normalized_shipment = {
                "tracking_number": tracking_number,
                "status": status,
                "events": normalized_events,
                "estimated_delivery_date": None,  # BRT doesn't provide estimated delivery
                "current_internal_state_id": current_internal_state_id,
            }
            
            return normalized_shipment
            
        except Exception as e:
            logger.error(f"Error normalizing BRT tracking data for {tracking_number}: {str(e)}")
            return None

