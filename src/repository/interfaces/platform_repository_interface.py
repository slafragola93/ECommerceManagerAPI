"""
Interfaccia per Platform Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.platform import Platform

class IPlatformRepository(IRepository[Platform, int]):
    """Interface per la repository dei platform"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Platform]:
        """Ottiene un platform per nome"""
        pass
    
    @abstractmethod
    def get_default(self) -> Optional[Platform]:
        """Ottiene la piattaforma di default (is_default = True)"""
        pass