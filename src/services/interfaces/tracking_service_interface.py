from abc import ABC, abstractmethod
from typing import List, Dict, Any


class ITrackingService(ABC):
    """Common interface for all tracking services (DHL, BRT, FedEx)"""
    
    @abstractmethod
    async def get_tracking(self, tracking_numbers: List[str], carrier_api_id: int) -> List[Dict[str, Any]]:
        """
        Get normalized tracking information for multiple shipments
        
        Args:
            tracking_numbers: List of tracking numbers to track
            carrier_api_id: Carrier API ID for authentication
            
        Returns:
            List of normalized tracking responses with format:
            {
                "tracking_number": str,
                "status": str,
                "events": List[Dict],
                "estimated_delivery_date": Optional[str],
                "current_internal_state_id": int
            }
        """
        pass

