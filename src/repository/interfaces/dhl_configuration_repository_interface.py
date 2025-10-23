from abc import ABC, abstractmethod
from typing import Optional
from src.models.dhl_configuration import DhlConfiguration


class IDhlConfigurationRepository(ABC):
    """Interface for DhlConfiguration repository operations"""
    
    @abstractmethod
    def get_by_carrier_api_id(self, id_carrier_api: int) -> Optional[DhlConfiguration]:
        """Retrieve DHL configuration by carrier_api_id"""
        pass