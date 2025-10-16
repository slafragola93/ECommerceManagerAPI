"""
Interfaccia per API Carrier Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.carrier_api import CarrierApi

class IApiCarrierRepository(IRepository[CarrierApi, int]):
    """Interface per la repository degli API carrier"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[CarrierApi]:
        """Ottiene un API carrier per nome"""
        pass
    
    @abstractmethod
    def get_by_account_number(self, account_number: int) -> Optional[CarrierApi]:
        """Ottiene un API carrier per numero account"""
        pass
