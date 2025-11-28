"""
Interfaccia per Carrier Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.carrier import Carrier

class ICarrierRepository(IRepository[Carrier, int]):
    """Interface per la repository dei carrier"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Carrier]:
        """Ottiene un carrier per nome"""
        pass
    
    @abstractmethod
    def get_price_by_criteria(self, id_carrier_api: int, id_country: int, weight: float, postcode: Optional[str] = None) -> Optional[float]:
        """Ottiene il prezzo del carrier price che corrisponde ai criteri specificati. Se postcode è fornito ma non trovato, cerca senza postcode"""
        pass