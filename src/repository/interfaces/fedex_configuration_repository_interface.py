from abc import abstractmethod
from typing import Optional
from src.core.interfaces import IRepository
from src.models.fedex_configuration import FedexConfiguration, FedexScopeEnum


class IFedexConfigurationRepository(IRepository[FedexConfiguration, int]):
    @abstractmethod
    def get_by_carrier_api_id(self, id_carrier_api: int) -> Optional[FedexConfiguration]:
        """Ritorna la prima configurazione trovata per id_carrier_api (per retrocompatibilità)"""
        pass
    
    @abstractmethod
    def get_by_carrier_api_id_and_scope(self, id_carrier_api: int, scope: FedexScopeEnum) -> Optional[FedexConfiguration]:
        """Ritorna la configurazione per id_carrier_api e scope specificato"""
        pass
