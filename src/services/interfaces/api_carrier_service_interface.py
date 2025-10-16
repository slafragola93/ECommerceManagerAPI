"""
Interfaccia per API Carrier Service seguendo ISP
"""
from abc import abstractmethod
from typing import List
from src.schemas.carrier_api_schema import CarrierApiSchema
from src.models.carrier_api import CarrierApi
from src.core.interfaces import IBaseService

class IApiCarrierService(IBaseService):
    """Interface per il servizio API carrier"""
    
    @abstractmethod
    async def create_api_carrier(self, api_carrier_data: CarrierApiSchema) -> CarrierApi:
        pass
    
    @abstractmethod
    async def update_api_carrier(self, api_carrier_id: int, api_carrier_data: CarrierApiSchema) -> CarrierApi:
        pass
    
    @abstractmethod
    async def get_api_carrier(self, api_carrier_id: int) -> CarrierApi:
        pass
    
    @abstractmethod
    async def get_api_carriers(self, page: int = 1, limit: int = 10, **filters) -> List[CarrierApi]:
        pass
    
    @abstractmethod
    async def delete_api_carrier(self, api_carrier_id: int) -> bool:
        pass
    
    @abstractmethod
    async def get_api_carriers_count(self, **filters) -> int:
        pass
