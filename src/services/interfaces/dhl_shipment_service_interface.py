from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class IDhlShipmentService(ABC):
    """Interface for DHL Shipment service operations"""
    
    @abstractmethod
    async def create_shipment(self, order_id: int) -> Dict[str, Any]:
        """Create DHL shipment for order"""
        pass
    
    @abstractmethod
    async def get_label_file_path(self, awb: str) -> Optional[str]:
        """Get label file path for AWB"""
        pass
