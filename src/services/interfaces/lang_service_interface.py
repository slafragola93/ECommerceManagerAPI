"""
Interfaccia per Lang Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.lang_schema import LangSchema, LangResponseSchema
from src.models.lang import Lang

class ILangService(IBaseService):
    """Interface per il servizio lang"""
    
    @abstractmethod
    async def create_lang(self, lang_data: LangSchema) -> Lang:
        """Crea un nuovo lang"""
        pass
    
    @abstractmethod
    async def update_lang(self, lang_id: int, lang_data: LangSchema) -> Lang:
        """Aggiorna un lang esistente"""
        pass
    
    @abstractmethod
    async def get_lang(self, lang_id: int) -> Lang:
        """Ottiene un lang per ID"""
        pass
    
    @abstractmethod
    async def get_langs(self, page: int = 1, limit: int = 10, **filters) -> List[Lang]:
        """Ottiene la lista dei lang con filtri"""
        pass
    
    @abstractmethod
    async def delete_lang(self, lang_id: int) -> bool:
        """Elimina un lang"""
        pass
    
    @abstractmethod
    async def get_langs_count(self, **filters) -> int:
        """Ottiene il numero totale di lang con filtri"""
        pass
