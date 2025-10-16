"""
Interfaccia per Brand Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.brand import Brand

class IBrandRepository(IRepository[Brand, int]):
    """Interface per la repository dei brand"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Brand]:
        """Ottiene un brand per nome"""
        pass
