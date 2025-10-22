from abc import ABC, abstractmethod
from typing import Optional
from src.schemas.brt_configuration_schema import (
    BrtConfigurationSchema,
    BrtConfigurationResponseSchema,
    BrtConfigurationUpdateSchema
)


class IBrtConfigurationService(ABC):
    @abstractmethod
    async def create_configuration(self, id_carrier_api: int, config_data: BrtConfigurationSchema) -> BrtConfigurationResponseSchema:
        pass
    
    @abstractmethod
    async def get_configuration_by_carrier(self, id_carrier_api: int) -> Optional[BrtConfigurationResponseSchema]:
        pass
    
    @abstractmethod
    async def update_configuration(self, id_carrier_api: int, config_data: BrtConfigurationUpdateSchema) -> BrtConfigurationResponseSchema:
        pass
    
    @abstractmethod
    async def delete_configuration(self, id_carrier_api: int) -> bool:
        pass
