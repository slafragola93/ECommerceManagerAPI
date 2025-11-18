from abc import ABC, abstractmethod
from typing import List, Dict, Any

from src.services.interfaces.tracking_service_interface import ITrackingService


class IDhlTrackingService(ITrackingService, ABC):
    """Interface for DHL Tracking service operations
    
    Extends ITrackingService to provide DHL-specific functionality.
    All DHL tracking services must implement both interfaces.
    """
    pass
