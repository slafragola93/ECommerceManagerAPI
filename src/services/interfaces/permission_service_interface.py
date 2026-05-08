"""
Interfaccia per Permission Service seguendo ISP
"""
from abc import abstractmethod
from typing import List
from src.core.interfaces import IBaseService
from src.schemas.permission_schema import (
    ModulePermissionResponseSchema,
    UserPermissionsResponseSchema,
    RolePermissionsResponseSchema,
    SaveUserPermissionsSchema,
    SaveRolePermissionsSchema
)


class IPermissionService(IBaseService):
    """
    Interfaccia per la gestione dei permessi granulari.
    Definisce i metodi che il PermissionService deve implementare.
    """

    @abstractmethod
    def check_permission(
        self,
        user_id: int,
        role_id: int,
        role_type: str,
        module_name: str,
        action: str
    ) -> bool:
        """
        Verifica se un utente può eseguire un'azione su un modulo.

        Logica a 4 livelli:
        1. role_type == 'full_crud' → True sempre (ADMIN)
        2. Permesso personale utente → usa i suoi flag
        3. Permesso del ruolo → usa i suoi flag
        4. Nessuna riga trovata → False

        action: 'read' | 'create' | 'update' | 'delete'
        """
        pass

    @abstractmethod
    def get_user_permissions(
        self,
        user_id: int
    ) -> UserPermissionsResponseSchema:
        """
        Restituisce la matrice completa dei permessi di un utente.
        Per ogni modulo mostra i 4 flag e la fonte (role/personal).
        Usato da GET /api/v1/users/{id}/permissions
        """
        pass

    @abstractmethod
    def save_user_permissions(
        self,
        user_id: int,
        payload: SaveUserPermissionsSchema,
        admin_id: int
    ) -> UserPermissionsResponseSchema:
        """
        Salva la matrice permessi di un utente.
        Verifica la password admin prima di procedere.
        Logga l'evento in auth_logs.
        Usato da PUT /api/v1/users/{id}/permissions
        """
        pass

    @abstractmethod
    def get_role_permissions(
        self,
        role_id: int
    ) -> RolePermissionsResponseSchema:
        """
        Restituisce la matrice completa dei permessi di un ruolo.
        Usato da GET /api/v1/roles/{id}/permissions
        """
        pass

    @abstractmethod
    def save_role_permissions(
        self,
        role_id: int,
        payload: SaveRolePermissionsSchema
    ) -> RolePermissionsResponseSchema:
        """
        Salva la matrice permessi di un ruolo.
        Usato da PUT /api/v1/roles/{id}/permissions
        """
        pass