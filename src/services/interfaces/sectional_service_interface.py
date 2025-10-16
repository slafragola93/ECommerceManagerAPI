"""
Interfaccia per Sectional Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.sectional_schema import SectionalSchema, SectionalResponseSchema
from src.models.sectional import Sectional

class ISectionalService(IBaseService):
    """Interface per il servizio sectional"""
    
    @abstractmethod
    async def create_sectional(self, sectional_data: SectionalSchema) -> Sectional:
        """Crea un nuovo sectional"""
        pass
    
    @abstractmethod
    async def update_sectional(self, sectional_id: int, sectional_data: SectionalSchema) -> Sectional:
        """Aggiorna un sectional esistente"""
        pass
    
    @abstractmethod
    async def get_sectional(self, sectional_id: int) -> Sectional:
        """Ottiene un sectional per ID"""
        pass
    
    @abstractmethod
    async def get_sectionals(self, page: int = 1, limit: int = 10, **filters) -> List[Sectional]:
        """Ottiene la lista dei sectional con filtri"""
        pass
    
    @abstractmethod
    async def delete_sectional(self, sectional_id: int) -> bool:
        """Elimina un sectional"""
        pass
    
    @abstractmethod
    async def get_sectionals_count(self, **filters) -> int:
        """Ottiene il numero totale di sectional con filtri"""
        pass
