"""
Interfaccia per Permission Repository seguendo ISP
"""
from abc import abstractmethod
from typing import Optional, List
from src.core.interfaces import IRepository
from src.models.user_module_permission import UserModulePermission


class IPermissionRepository(IRepository[UserModulePermission, int]):
    """
    Interfaccia per la repository dei permessi granulari.
    Gestisce le query su user_module_permissions.
    """

    @abstractmethod
    def get_user_permission(
        self,
        user_id: int,
        module_id: int
    ) -> Optional[UserModulePermission]:
        """
        Cerca il permesso personale di un utente su un modulo.
        Riga con id_user valorizzato e id_role NULL.
        """
        pass

    @abstractmethod
    def get_role_permission(
        self,
        role_id: int,
        module_id: int
    ) -> Optional[UserModulePermission]:
        """
        Cerca il permesso di default di un ruolo su un modulo.
        Riga con id_role valorizzato e id_user NULL.
        """
        pass

    @abstractmethod
    def get_all_user_permissions(
        self,
        user_id: int
    ) -> List[UserModulePermission]:
        """
        Restituisce tutti i permessi personali di un utente.
        Usato per costruire la matrice completa.
        """
        pass

    @abstractmethod
    def get_all_role_permissions(
        self,
        role_id: int
    ) -> List[UserModulePermission]:
        """
        Restituisce tutti i permessi di un ruolo.
        Usato per costruire la matrice completa del ruolo.
        """
        pass

    @abstractmethod
    def save_user_permissions(
        self,
        user_id: int,
        module_id: int,
        can_read: bool,
        can_create: bool,
        can_update: bool,
        can_delete: bool,
        created_by: int
    ) -> UserModulePermission:
        """
        Crea o aggiorna il permesso personale di un utente su un modulo.
        Se la riga esiste già la aggiorna, altrimenti la crea (upsert).
        """
        pass

    @abstractmethod
    def save_role_permissions(
        self,
        role_id: int,
        module_id: int,
        can_read: bool,
        can_create: bool,
        can_update: bool,
        can_delete: bool
    ) -> UserModulePermission:
        """
        Crea o aggiorna il permesso di un ruolo su un modulo.
        Se la riga esiste già la aggiorna, altrimenti la crea (upsert).
        """
        pass

    @abstractmethod
    def delete_user_permissions(
        self,
        user_id: int
    ) -> bool:
        """
        Elimina tutti i permessi personali di un utente.
        Usato quando si vuole resettare la matrice dell'utente.
        """
        pass

    @abstractmethod
    def delete_role_permissions(
        self,
        role_id: int
    ) -> bool:
        """
        Elimina tutti i permessi di un ruolo.
        Usato quando si elimina un ruolo.
        """
        pass