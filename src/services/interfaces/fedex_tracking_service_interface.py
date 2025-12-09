from abc import ABC, abstractmethod
from typing import List, Dict, Any

from src.services.interfaces.tracking_service_interface import ITrackingService


class IFedexTrackingService(ITrackingService, ABC):
    """Interface for FedEx Tracking service operations
    
    Extends ITrackingService to provide FedEx-specific functionality.
    All FedEx tracking services must implement both interfaces.
    """
    pass

