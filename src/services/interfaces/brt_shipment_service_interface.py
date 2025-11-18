from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from src.services.interfaces.shipment_service_interface import IShipmentService


class IBrtShipmentService(IShipmentService, ABC):
    """Interface for BRT Shipment service operations
    
    Extends IShipmentService to provide BRT-specific functionality.
    All BRT shipment services must implement both interfaces.
    """
    pass

