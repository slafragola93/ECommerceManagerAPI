"""
Interfaccia per Sectional Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.sectional import Sectional

class ISectionalRepository(IRepository[Sectional, int]):
    """Interface per la repository dei sectional"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Sectional]:
        """Ottiene un sectional per nome"""
        pass
