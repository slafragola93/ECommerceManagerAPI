"""
Interfaccia per Sectional Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List, Union
from src.core.interfaces import IRepository
from src.models.sectional import Sectional
from src.schemas.sectional_schema import SectionalSchema

class ISectionalRepository(IRepository[Sectional, int]):
    """Interface per la repository dei sectional"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Sectional]:
        """Ottiene un sectional per nome"""
        pass
    
    @abstractmethod
    def create_and_get_id(self, data: Union[SectionalSchema, dict]) -> int:
        """Crea un sectional e restituisce l'ID. Se esiste già uno con lo stesso nome, restituisce l'ID esistente."""
        pass
