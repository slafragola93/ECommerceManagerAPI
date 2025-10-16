"""
Interfaccia per Configuration Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.configuration_schema import ConfigurationSchema, ConfigurationResponseSchema
from src.models.configuration import Configuration

class IConfigurationService(IBaseService):
    """Interface per il servizio configuration"""
    
    @abstractmethod
    async def create_configuration(self, configuration_data: ConfigurationSchema) -> Configuration:
        """Crea un nuovo configuration"""
        pass
    
    @abstractmethod
    async def update_configuration(self, configuration_id: int, configuration_data: ConfigurationSchema) -> Configuration:
        """Aggiorna un configuration esistente"""
        pass
    
    @abstractmethod
    async def get_configuration(self, configuration_id: int) -> Configuration:
        """Ottiene un configuration per ID"""
        pass
    
    @abstractmethod
    async def get_configurations(self, page: int = 1, limit: int = 10, **filters) -> List[Configuration]:
        """Ottiene la lista dei configuration con filtri"""
        pass
    
    @abstractmethod
    async def delete_configuration(self, configuration_id: int) -> bool:
        """Elimina un configuration"""
        pass
    
    @abstractmethod
    async def get_configurations_count(self, **filters) -> int:
        """Ottiene il numero totale di configuration con filtri"""
        pass
