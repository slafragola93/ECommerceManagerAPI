from abc import abstractmethod
from typing import Optional
from src.core.interfaces import IRepository
from src.models.brt_configuration import BrtConfiguration


class IBrtConfigurationRepository(IRepository[BrtConfiguration, int]):
    @abstractmethod
    def get_by_carrier_api_id(self, id_carrier_api: int) -> Optional[BrtConfiguration]:
        """Relazione 1:1, ritorna Optional[BrtConfiguration]"""
        pass
