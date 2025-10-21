"""
Interfaccia per AppConfiguration Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.app_configuration import AppConfiguration

class IAppConfigurationRepository(IRepository[AppConfiguration, int]):
    """Interface per la repository dei app_configuration"""
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[AppConfiguration]:
        """Ottiene un app_configuration per nome"""
        pass
    
    @abstractmethod
    def get_by_name_and_category(self, name: str, category: str) -> Optional[AppConfiguration]:
        """Ottiene un app_configuration per nome e categoria"""
        pass
    
    @abstractmethod
    def get_by_category(self, category: str) -> List[AppConfiguration]:
        """Ottiene tutte le configurazioni per categoria"""
        pass