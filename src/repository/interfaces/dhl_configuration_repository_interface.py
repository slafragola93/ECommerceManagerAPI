from abc import abstractmethod
from typing import Optional
from src.core.interfaces import IRepository
from src.models.dhl_configuration import DhlConfiguration


class IDhlConfigurationRepository(IRepository[DhlConfiguration, int]):
    @abstractmethod
    def get_by_carrier_api_id(self, id_carrier_api: int) -> Optional[DhlConfiguration]:
        """Relazione 1:1, ritorna Optional[DhlConfiguration]"""
        pass
