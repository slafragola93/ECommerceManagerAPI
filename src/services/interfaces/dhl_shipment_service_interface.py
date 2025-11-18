from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from src.services.interfaces.shipment_service_interface import IShipmentService


class IDhlShipmentService(IShipmentService, ABC):
    """Interface for DHL Shipment service operations
    
    Extends IShipmentService to provide DHL-specific functionality.
    All DHL shipment services must implement both interfaces.
    """
    pass
