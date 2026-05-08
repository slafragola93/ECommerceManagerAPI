"""
Permission Repository seguendo SOLID
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.models.user_module_permission import UserModulePermission
from src.repository.interfaces.permission_repository_interface import IPermissionRepository
from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException


class PermissionRepository(BaseRepository[UserModulePermission, int], IPermissionRepository):
    """Repository per la gestione dei permessi granulari per modulo"""

    def __init__(self, session: Session):
        super().__init__(session, UserModulePermission)

    def get_user_permission(
        self,
        user_id: int,
        module_id: int
    ) -> Optional[UserModulePermission]:
        """
        Cerca il permesso personale di un utente su un modulo.
        Riga con id_user valorizzato e id_role NULL.
        """
        try:
            return self._session.query(UserModulePermission).filter(
                and_(
                    UserModulePermission.id_user == user_id,
                    UserModulePermission.id_module == module_id,
                    UserModulePermission.id_role.is_(None)
                )
            ).first()
        except Exception as e:
            raise InfrastructureException(
                f"Errore nel recupero permesso utente: {str(e)}"
            )

    def get_role_permission(
        self,
        role_id: int,
        module_id: int
    ) -> Optional[UserModulePermission]:
        """
        Cerca il permesso di default di un ruolo su un modulo.
        Riga con id_role valorizzato e id_user NULL.
        """
        try:
            return self._session.query(UserModulePermission).filter(
                and_(
                    UserModulePermission.id_role == role_id,
                    UserModulePermission.id_module == module_id,
                    UserModulePermission.id_user.is_(None)
                )
            ).first()
        except Exception as e:
            raise InfrastructureException(
                f"Errore nel recupero permesso ruolo: {str(e)}"
            )

    def get_all_user_permissions(
        self,
        user_id: int
    ) -> List[UserModulePermission]:
        """
        Restituisce tutti i permessi personali di un utente.
        Usato per costruire la matrice completa.
        """
        try:
            return self._session.query(UserModulePermission).filter(
                and_(
                    UserModulePermission.id_user == user_id,
                    UserModulePermission.id_role.is_(None)
                )
            ).all()
        except Exception as e:
            raise InfrastructureException(
                f"Errore nel recupero permessi utente: {str(e)}"
            )

    def get_all_role_permissions(
        self,
        role_id: int
    ) -> List[UserModulePermission]:
        """
        Restituisce tutti i permessi di un ruolo.
        Usato per costruire la matrice completa del ruolo.
        """
        try:
            return self._session.query(UserModulePermission).filter(
                and_(
                    UserModulePermission.id_role == role_id,
                    UserModulePermission.id_user.is_(None)
                )
            ).all()
        except Exception as e:
            raise InfrastructureException(
                f"Errore nel recupero permessi ruolo: {str(e)}"
            )

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
        Upsert permesso personale utente su un modulo.
        Se esiste aggiorna, altrimenti crea.
        """
        try:
            existing = self.get_user_permission(user_id, module_id)

            if existing:
                existing.can_read   = can_read
                existing.can_create = can_create
                existing.can_update = can_update
                existing.can_delete = can_delete
                existing.updated_at = datetime.utcnow()
                self._session.commit()
                self._session.refresh(existing)
                return existing
            else:
                new_perm = UserModulePermission(
                    id_user    = user_id,
                    id_module  = module_id,
                    id_role    = None,
                    can_read   = can_read,
                    can_create = can_create,
                    can_update = can_update,
                    can_delete = can_delete,
                    created_by = created_by,
                    updated_at = datetime.utcnow()
                )
                self._session.add(new_perm)
                self._session.commit()
                self._session.refresh(new_perm)
                return new_perm

        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(
                f"Errore nel salvataggio permesso utente: {str(e)}"
            )

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
        Upsert permesso ruolo su un modulo.
        Se esiste aggiorna, altrimenti crea.
        """
        try:
            existing = self.get_role_permission(role_id, module_id)

            if existing:
                existing.can_read   = can_read
                existing.can_create = can_create
                existing.can_update = can_update
                existing.can_delete = can_delete
                existing.updated_at = datetime.utcnow()
                self._session.commit()
                self._session.refresh(existing)
                return existing
            else:
                new_perm = UserModulePermission(
                    id_role    = role_id,
                    id_module  = module_id,
                    id_user    = None,
                    can_read   = can_read,
                    can_create = can_create,
                    can_update = can_update,
                    can_delete = can_delete,
                    updated_at = datetime.utcnow()
                )
                self._session.add(new_perm)
                self._session.commit()
                self._session.refresh(new_perm)
                return new_perm

        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(
                f"Errore nel salvataggio permesso ruolo: {str(e)}"
            )

    def delete_user_permissions(self, user_id: int) -> bool:
        """Elimina tutti i permessi personali di un utente"""
        try:
            self._session.query(UserModulePermission).filter(
                and_(
                    UserModulePermission.id_user == user_id,
                    UserModulePermission.id_role.is_(None)
                )
            ).delete()
            self._session.commit()
            return True
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(
                f"Errore nell'eliminazione permessi utente: {str(e)}"
            )

    def delete_role_permissions(self, role_id: int) -> bool:
        """Elimina tutti i permessi di un ruolo"""
        try:
            self._session.query(UserModulePermission).filter(
                and_(
                    UserModulePermission.id_role == role_id,
                    UserModulePermission.id_user.is_(None)
                )
            ).delete()
            self._session.commit()
            return True
        except Exception as e:
            self._session.rollback()
            raise InfrastructureException(
                f"Errore nell'eliminazione permessi ruolo: {str(e)}"
            )

    def get_all(self, **filters) -> List[UserModulePermission]:
        """Implementazione richiesta da BaseRepository"""
        try:
            return self._session.query(UserModulePermission).all()
        except Exception as e:
            raise InfrastructureException(
                f"Errore nel recupero permessi: {str(e)}"
            )

    def get_count(self, **filters) -> int:
        """Implementazione richiesta da BaseRepository"""
        try:
            return self._session.query(UserModulePermission).count()
        except Exception as e:
            raise InfrastructureException(
                f"Errore nel conteggio permessi: {str(e)}"
            )