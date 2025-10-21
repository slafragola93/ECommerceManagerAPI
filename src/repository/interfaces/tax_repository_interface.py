"""
Interfaccia per Tax Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.tax import Tax

class ITaxRepository(IRepository[Tax, int]):
    """Interface per la repository dei tax"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Tax]:
        """Ottiene un tax per nome"""
        pass
    
    @abstractmethod
    def define_tax(self, country_id: int) -> int:
        """Definisce la tassa da applicare basata sul paese"""
        pass