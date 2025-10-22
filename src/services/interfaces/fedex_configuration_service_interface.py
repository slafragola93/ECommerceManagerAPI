from abc import ABC, abstractmethod
from typing import Optional
from src.schemas.fedex_configuration_schema import (
    FedexConfigurationSchema,
    FedexConfigurationResponseSchema,
    FedexConfigurationUpdateSchema
)


class IFedexConfigurationService(ABC):
    @abstractmethod
    async def create_configuration(self, id_carrier_api: int, config_data: FedexConfigurationSchema) -> FedexConfigurationResponseSchema:
        pass
    
    @abstractmethod
    async def get_configuration_by_carrier(self, id_carrier_api: int) -> Optional[FedexConfigurationResponseSchema]:
        pass
    
    @abstractmethod
    async def update_configuration(self, id_carrier_api: int, config_data: FedexConfigurationUpdateSchema) -> FedexConfigurationResponseSchema:
        pass
    
    @abstractmethod
    async def delete_configuration(self, id_carrier_api: int) -> bool:
        pass
