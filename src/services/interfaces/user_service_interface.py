"""
Interfaccia per User Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.user_schema import UserSchema, UserResponseSchema
from src.models.user import User

class IUserService(IBaseService):
    """Interface per il servizio utenti"""
    
    @abstractmethod
    async def create_user(self, user_data: UserSchema) -> User:
        """Crea un nuovo utente"""
        pass
    
    @abstractmethod
    async def update_user(self, user_id: int, user_data: UserSchema) -> User:
        """Aggiorna un utente esistente"""
        pass
    
    @abstractmethod
    async def get_user(self, user_id: int) -> User:
        """Ottiene un utente per ID"""
        pass
    
    @abstractmethod
    async def get_users(self, page: int = 1, limit: int = 10, **filters) -> List[User]:
        """Ottiene la lista degli utenti con filtri"""
        pass
    
    @abstractmethod
    async def delete_user(self, user_id: int) -> bool:
        """Elimina un utente"""
        pass
    
    @abstractmethod
    async def get_users_count(self, **filters) -> int:
        """Ottiene il numero totale di utenti con filtri"""
        pass
