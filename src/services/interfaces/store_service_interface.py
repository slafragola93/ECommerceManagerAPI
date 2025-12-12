"""
Interfaccia per Store Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.store_schema import StoreSchema, StoreResponseSchema, StoreCreateSchema, StoreUpdateSchema
from src.models.store import Store

class IStoreService(IBaseService):
    """Interface per il servizio store"""
    
    @abstractmethod
    async def create_store(self, store_data: StoreCreateSchema) -> Store:
        """Crea un nuovo store"""
        pass
    
    @abstractmethod
    async def update_store(self, store_id: int, store_data: StoreUpdateSchema) -> Store:
        """Aggiorna uno store esistente"""
        pass
    
    @abstractmethod
    async def get_store(self, store_id: int) -> Store:
        """Ottiene uno store per ID"""
        pass
    
    @abstractmethod
    async def get_stores(self, page: int = 1, limit: int = 10, **filters) -> List[Store]:
        """Ottiene la lista degli store con filtri"""
        pass
    
    @abstractmethod
    async def delete_store(self, store_id: int) -> bool:
        """Elimina uno store"""
        pass
    
    @abstractmethod
    async def get_stores_count(self, **filters) -> int:
        """Ottiene il numero totale di store con filtri"""
        pass
    
    @abstractmethod
    async def get_default_store(self) -> Store:
        """Ottiene lo store di default"""
        pass

