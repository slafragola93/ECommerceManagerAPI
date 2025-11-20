from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class IShipmentService(ABC):
    """Common interface for all shipment services (DHL, BRT, FedEx)"""
    
    @abstractmethod
    async def create_shipment(self, order_id: int) -> Dict[str, Any]:
        """
        Create shipment for order
        
        Args:
            order_id: Order ID to create shipment for
            
        Returns:
            Dict with shipment details, must include 'awb' key
        """
        pass
    
    @abstractmethod
    async def get_label_file_path(self, awb: str) -> Optional[str]:
        """
        Get label file path for AWB
        
        Args:
            awb: Air Waybill number or tracking number
            
        Returns:
            File path to label PDF or None if not found
        """
        pass
    
    @abstractmethod
    async def cancel_shipment(self, order_id: int) -> Dict[str, Any]:
        """
        Cancel shipment for order
        
        Args:
            order_id: Order ID to cancel shipment for
            
        Returns:
            Dict with cancellation result
        """
        pass

