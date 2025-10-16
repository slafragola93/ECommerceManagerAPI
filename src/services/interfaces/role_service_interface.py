"""
Interfaccia per Role Service seguendo ISP
"""
from abc import ABC, abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.role_schema import RoleSchema, RoleResponseSchema
from src.models.role import Role

class IRoleService(IBaseService):
    """Interface per il servizio ruoli"""
    
    @abstractmethod
    async def create_role(self, role_data: RoleSchema) -> Role:
        """Crea un nuovo ruolo"""
        pass
    
    @abstractmethod
    async def update_role(self, role_id: int, role_data: RoleSchema) -> Role:
        """Aggiorna un ruolo esistente"""
        pass
    
    @abstractmethod
    async def get_role(self, role_id: int) -> Role:
        """Ottiene un ruolo per ID"""
        pass
    
    @abstractmethod
    async def get_roles(self, page: int = 1, limit: int = 10, **filters) -> List[Role]:
        """Ottiene la lista dei ruoli con filtri"""
        pass
    
    @abstractmethod
    async def delete_role(self, role_id: int) -> bool:
        """Elimina un ruolo"""
        pass
    
    @abstractmethod
    async def get_roles_count(self, **filters) -> int:
        """Ottiene il numero totale di ruoli con filtri"""
        pass
