from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from src.services.interfaces.shipment_service_interface import IShipmentService


class IFedexShipmentService(IShipmentService, ABC):
    """Interface for FedEx Shipment service operations
    
    Extends IShipmentService to provide FedEx-specific functionality.
    All FedEx shipment services must implement both interfaces.
    """
    pass

