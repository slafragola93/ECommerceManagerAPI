"""
Interfaccia per Carrier Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from src.core.interfaces import IBaseService
from src.schemas.carrier_schema import CarrierSchema, CarrierResponseSchema
from src.models.carrier import Carrier

class ICarrierService(IBaseService):
    """Interface per il servizio carrier"""
    
    @abstractmethod
    async def create_carrier(self, carrier_data: CarrierSchema) -> Carrier:
        """Crea un nuovo carrier"""
        pass
    
    @abstractmethod
    async def update_carrier(self, carrier_id: int, carrier_data: CarrierSchema) -> Carrier:
        """Aggiorna un carrier esistente"""
        pass
    
    @abstractmethod
    async def get_carrier(self, carrier_id: int) -> Carrier:
        """Ottiene un carrier per ID"""
        pass
    
    @abstractmethod
    async def get_carriers(self, page: int = 1, limit: int = 10, **filters) -> List[Carrier]:
        """Ottiene la lista dei carrier con filtri"""
        pass
    
    @abstractmethod
    async def delete_carrier(self, carrier_id: int) -> bool:
        """Elimina un carrier"""
        pass
    
    @abstractmethod
    async def get_carriers_count(self, **filters) -> int:
        """Ottiene il numero totale di carrier con filtri"""
        pass
    
    @abstractmethod
    async def get_carrier_price(self, id_carrier_api: int, id_country: int, weight: float, postcode: Optional[str] = None) -> float:
        """Recupera il prezzo del corriere basato sui criteri specificati. Se postcode è fornito ma non trovato, cerca senza postcode"""
        pass
