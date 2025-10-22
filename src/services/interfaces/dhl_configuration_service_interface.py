from abc import ABC, abstractmethod
from typing import Optional
from src.schemas.dhl_configuration_schema import (
    DhlConfigurationSchema,
    DhlConfigurationResponseSchema,
    DhlConfigurationUpdateSchema
)


class IDhlConfigurationService(ABC):
    @abstractmethod
    async def create_configuration(self, id_carrier_api: int, config_data: DhlConfigurationSchema) -> DhlConfigurationResponseSchema:
        pass
    
    @abstractmethod
    async def get_configuration_by_carrier(self, id_carrier_api: int) -> Optional[DhlConfigurationResponseSchema]:
        pass
    
    @abstractmethod
    async def update_configuration(self, id_carrier_api: int, config_data: DhlConfigurationUpdateSchema) -> DhlConfigurationResponseSchema:
        pass
    
    @abstractmethod
    async def delete_configuration(self, id_carrier_api: int) -> bool:
        pass
