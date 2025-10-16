"""
Interfaccia per Configuration Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.configuration import Configuration

class IConfigurationRepository(IRepository[Configuration, int]):
    """Interface per la repository dei configuration"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Configuration]:
        """Ottiene un configuration per nome"""
        pass
