from abc import ABC, abstractmethod
from typing import List
from datetime import datetime
from src.models.shipment_document import ShipmentDocument


class IShipmentDocumentRepository(ABC):
    """Interface for ShipmentDocument repository operations"""
    
    @abstractmethod
    def get_expired_documents(self) -> List[ShipmentDocument]:
        """Get all expired shipment documents"""
        pass
    
    @abstractmethod
    def get_by_order_id(self, order_id: int) -> List[ShipmentDocument]:
        """Get all shipment documents for a specific order"""
        pass
    
    @abstractmethod
    def get_by_awb(self, awb: str) -> List[ShipmentDocument]:
        """Get all shipment documents for a specific AWB"""
        pass
    
    @abstractmethod
    def delete_by_id(self, document_id: int) -> bool:
        """Delete a shipment document by ID"""
        pass

