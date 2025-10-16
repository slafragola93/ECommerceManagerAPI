"""
Interfaccia per Role Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.role import Role

class IRoleRepository(IRepository[Role, int]):
    """Interface per la repository dei ruoli"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Role]:
        """Ottiene un ruolo per nome"""
        pass
