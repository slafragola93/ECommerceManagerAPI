"""
Interfaccia per AppConfiguration Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.app_configuration_schema import AppConfigurationSchema, AppConfigurationResponseSchema
from src.models.app_configuration import AppConfiguration

class IAppConfigurationService(IBaseService):
    """Interface per il servizio app_configuration"""
    
    @abstractmethod
    async def create_app_configuration(self, app_configuration_data: AppConfigurationSchema) -> AppConfiguration:
        """Crea un nuovo app_configuration"""
        pass
    
    @abstractmethod
    async def update_app_configuration(self, app_configuration_id: int, app_configuration_data: AppConfigurationSchema) -> AppConfiguration:
        """Aggiorna un app_configuration esistente"""
        pass
    
    @abstractmethod
    async def get_app_configuration(self, app_configuration_id: int) -> AppConfiguration:
        """Ottiene un app_configuration per ID"""
        pass
    
    @abstractmethod
    async def get_app_configurations(self, page: int = 1, limit: int = 10, **filters) -> List[AppConfiguration]:
        """Ottiene la lista dei app_configuration con filtri"""
        pass
    
    @abstractmethod
    async def delete_app_configuration(self, app_configuration_id: int) -> bool:
        """Elimina un app_configuration"""
        pass
    
    @abstractmethod
    async def get_app_configurations_count(self, **filters) -> int:
        """Ottiene il numero totale di app_configuration con filtri"""
        pass

    @abstractmethod
    async def get_app_configurations_by_category(self, category: str) -> List[AppConfiguration]:
        """Ottiene tutte le configurazioni per categoria"""
        pass
