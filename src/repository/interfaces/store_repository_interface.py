"""
Interfaccia per Store Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.store import Store

class IStoreRepository(IRepository[Store, int]):
    """Interface per la repository degli store"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Store]:
        """Ottiene uno store per nome"""
        pass
    
    @abstractmethod
    def get_default(self) -> Optional[Store]:
        """Ottiene lo store di default (is_default = True)"""
        pass
    
    @abstractmethod
    def get_by_platform(self, id_platform: int) -> List[Store]:
        """Ottiene tutti gli store per una piattaforma"""
        pass
    
    @abstractmethod
    def get_by_vat_number(self, vat_number: str) -> Optional[Store]:
        """Ottiene uno store per partita IVA"""
        pass
    
    @abstractmethod
    def get_active_stores(self) -> List[Store]:
        """Ottiene tutti gli store attivi"""
        pass

