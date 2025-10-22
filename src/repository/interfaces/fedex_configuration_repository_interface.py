from abc import abstractmethod
from typing import Optional
from src.core.interfaces import IRepository
from src.models.fedex_configuration import FedexConfiguration


class IFedexConfigurationRepository(IRepository[FedexConfiguration, int]):
    @abstractmethod
    def get_by_carrier_api_id(self, id_carrier_api: int) -> Optional[FedexConfiguration]:
        """Relazione 1:1, ritorna Optional[FedexConfiguration]"""
        pass
