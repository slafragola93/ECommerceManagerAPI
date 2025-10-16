"""
Interfaccia per User Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.user import User

class IUserRepository(IRepository[User, int]):
    """Interface per la repository degli utenti"""
    
    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]:
        """Ottiene un utente per email"""
        pass
    
    @abstractmethod
    def get_by_username(self, username: str) -> Optional[User]:
        """Ottiene un utente per username"""
        pass
