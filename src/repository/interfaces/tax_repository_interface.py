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
    
    @abstractmethod
    def get_percentage_by_id(self, id_tax: int) -> float:
        """Ottiene la percentuale di una tassa per ID"""
        pass
    
    @abstractmethod
    def get_tax_by_id(self, id_tax: int) -> Optional[Tax]:
        """Ottiene una Tax per ID"""
        pass
    
    @abstractmethod
    def get_tax_by_id_country(self, id_country: int) -> Optional[Tax]:
        """Ottiene una Tax basata su id_country"""
        pass