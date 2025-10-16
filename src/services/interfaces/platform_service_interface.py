"""
Interfaccia per Platform Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.platform_schema import PlatformSchema, PlatformResponseSchema
from src.models.platform import Platform

class IPlatformService(IBaseService):
    """Interface per il servizio platform"""
    
    @abstractmethod
    async def create_platform(self, platform_data: PlatformSchema) -> Platform:
        """Crea un nuovo platform"""
        pass
    
    @abstractmethod
    async def update_platform(self, platform_id: int, platform_data: PlatformSchema) -> Platform:
        """Aggiorna un platform esistente"""
        pass
    
    @abstractmethod
    async def get_platform(self, platform_id: int) -> Platform:
        """Ottiene un platform per ID"""
        pass
    
    @abstractmethod
    async def get_platforms(self, page: int = 1, limit: int = 10, **filters) -> List[Platform]:
        """Ottiene la lista dei platform con filtri"""
        pass
    
    @abstractmethod
    async def delete_platform(self, platform_id: int) -> bool:
        """Elimina un platform"""
        pass
    
    @abstractmethod
    async def get_platforms_count(self, **filters) -> int:
        """Ottiene il numero totale di platform con filtri"""
        pass
