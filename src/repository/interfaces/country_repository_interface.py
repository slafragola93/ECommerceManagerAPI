"""
Interfaccia per Country Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.country import Country

class ICountryRepository(IRepository[Country, int]):
    """Interface per la repository dei country"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Country]:
        """Ottiene un country per nome"""
        pass
