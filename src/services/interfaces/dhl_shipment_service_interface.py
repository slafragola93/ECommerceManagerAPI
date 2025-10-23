from abc import ABC, abstractmethod
from typing import Dict, Any


class IDhlShipmentService(ABC):
    """Interface for DHL Shipment service operations"""
    
    @abstractmethod
    async def create_shipment(self, order_id: int) -> Dict[str, Any]:
        """Create DHL shipment for order"""
        pass
