"""
Interfaccia per Lang Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.lang import Lang

class ILangRepository(IRepository[Lang, int]):
    """Interface per la repository dei lang"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Lang]:
        """Ottiene un lang per nome"""
        pass
    
    @abstractmethod
    def get_by_iso_code(self, iso_code: str) -> Optional[Lang]:
        """Ottiene un lang per codice ISO"""
        pass