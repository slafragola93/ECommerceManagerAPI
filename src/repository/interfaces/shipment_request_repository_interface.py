from abc import ABC, abstractmethod
from typing import Optional
from src.models.shipment_request import ShipmentRequest


class IShipmentRequestRepository(ABC):
    """Interface for ShipmentRequest repository operations"""
    
    @abstractmethod
    def get_by_message_reference(self, message_ref: str) -> Optional[ShipmentRequest]:
        """Get shipment request by message reference for idempotency check"""
        pass
    
    @abstractmethod
    def cleanup_expired(self) -> int:
        """Remove expired shipment request records and return count of deleted records"""
        pass
