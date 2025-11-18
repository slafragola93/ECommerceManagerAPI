from abc import ABC, abstractmethod
from typing import List, Dict, Any

from src.services.interfaces.tracking_service_interface import ITrackingService


class IBrtTrackingService(ITrackingService, ABC):
    """Interface for BRT Tracking service operations
    
    Extends ITrackingService to provide BRT-specific functionality.
    All BRT tracking services must implement both interfaces.
    """
    pass

