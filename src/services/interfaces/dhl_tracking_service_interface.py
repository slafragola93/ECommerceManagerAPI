from abc import ABC, abstractmethod
from typing import List, Dict, Any


class IDhlTrackingService(ABC):
    """Interface for DHL Tracking service operations"""
    
    @abstractmethod
    async def get_tracking(self, tracking_numbers: List[str], carrier_api_id: int) -> List[Dict[str, Any]]:
        """Get normalized tracking info"""
        pass
