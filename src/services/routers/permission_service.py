"""
Permission Service - Logica centrale per la gestione
dei permessi granulari per modulo.
"""
from typing import Any, List
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from src.models.user import User
from src.models.app_modules import AppModule
from src.models.role import PermissionType
from src.repository.interfaces.permission_repository_interface import IPermissionRepository
from src.repository.interfaces.user_repository_interface import IUserRepository
from src.repository.interfaces.role_repository_interface import IRoleRepository
from src.schemas.permission_schema import (
    ModulePermissionResponseSchema,
    UserPermissionsResponseSchema,
    RolePermissionsResponseSchema,
    SaveUserPermissionsSchema,
    SaveRolePermissionsSchema
)
from src.services.interfaces.permission_service_interface import IPermissionService
from src.core.exceptions import (
    ValidationException,
    NotFoundException,
    AuthenticationException,
    BusinessRuleException
)

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class PermissionService(IPermissionService):
    """
    Service per la gestione dei permessi granulari.
    Implementa la logica a 4 livelli per il controllo accessi.
    """

    def __init__(
        self,
        permission_repository: IPermissionRepository = None,
        user_repository: IUserRepository = None,
        role_repository: IRoleRepository = None,
        db: Session = None
    ):
        self._permission_repo = permission_repository
        self._user_repo = user_repository
        self._role_repo = role_repository
        self._db = db

    # ──────────────────────────────────────────────────────
    # METODO PRINCIPALE — chiamato ad ogni richiesta protetta
    # ──────────────────────────────────────────────────────

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
        1. ADMIN (full_crud) → True sempre
        2. Override personale → usa i suoi flag
        3. Permesso del ruolo → usa i suoi flag
        4. Nessuna riga → False
        """

        # ── Livello 1 — ADMIN bypassa tutto ───────────────
        if role_type == PermissionType.full_crud.value:
            return True

        # ── Carica il modulo per ottenere l'id ────────────
        module = self._db.query(AppModule).filter(
            AppModule.name == module_name,
            AppModule.is_active == True
        ).first()

        if not module:
            return False  # modulo inesistente o disattivato

        # ── Livello 2 — Override personale ────────────────
        personal = self._permission_repo.get_user_permission(
            user_id, module.id_module
        )
        if personal is not None:
            return self._get_flag(personal, action)

        # ── Livello 3 — Permesso del ruolo ────────────────
        role_perm = self._permission_repo.get_role_permission(
            role_id, module.id_module
        )
        if role_perm is not None:
            return self._get_flag(role_perm, action)

        # ── Livello 4 — Nessuna riga trovata ──────────────
        return False

    # ──────────────────────────────────────────────────────
    # MATRICE UTENTE
    # ──────────────────────────────────────────────────────

    def get_user_permissions(
        self,
        user_id: int
    ) -> UserPermissionsResponseSchema:
        """
        Costruisce la matrice completa dei permessi di un utente.
        Per ogni modulo mostra i 4 flag e la fonte.

        Casi speciali:
        - Utente senza ruolo → matrice vuota (no crash)
        - Utente con ruolo full_crud → tutti i flag a True
        """
        user = self._user_repo.get_by_id_or_raise(user_id)
        role = user.roles[0] if user.roles else None

        # Carica tutti i moduli attivi
        modules = self._db.query(AppModule).filter(
            AppModule.is_active == True
        ).order_by(AppModule.sort_order).all()

        # ── Caso speciale: utente senza ruolo → matrice vuota ──
        if not role:
            permissions = [
                ModulePermissionResponseSchema(
                    module_name = module.name,
                    label       = module.label,
                    can_read    = False,
                    can_create  = False,
                    can_update  = False,
                    can_delete  = False,
                    source      = 'none'
                )
                for module in modules
            ]
            return UserPermissionsResponseSchema(
                id_user     = user.id_user,
                username    = user.username,
                role_name   = '',
                role_type   = 'custom',
                permissions = permissions
            )

        # ── Caso speciale: ruolo full_crud → tutti i flag True ──
        if role.permission_type.value == PermissionType.full_crud.value:
            permissions = [
                ModulePermissionResponseSchema(
                    module_name = module.name,
                    label       = module.label,
                    can_read    = True,
                    can_create  = True,
                    can_update  = True,
                    can_delete  = True,
                    source      = 'full_crud'
                )
                for module in modules
            ]
            return UserPermissionsResponseSchema(
                id_user     = user.id_user,
                username    = user.username,
                role_name   = role.name,
                role_type   = role.permission_type.value,
                permissions = permissions
            )

        # ── Logica standard per ruoli custom ──
        personal_perms = self._permission_repo.get_all_user_permissions(user_id)
        personal_map = {p.id_module: p for p in personal_perms}

        role_perms = self._permission_repo.get_all_role_permissions(role.id_role)
        role_map = {p.id_module: p for p in role_perms}

        permissions = []
        for module in modules:

            if module.id_module in personal_map:
                perm = personal_map[module.id_module]
                source = 'personal'
            elif module.id_module in role_map:
                perm = role_map[module.id_module]
                source = 'role'
            else:
                permissions.append(ModulePermissionResponseSchema(
                    module_name = module.name,
                    label       = module.label,
                    can_read    = False,
                    can_create  = False,
                    can_update  = False,
                    can_delete  = False,
                    source      = 'none'
                ))
                continue

            permissions.append(ModulePermissionResponseSchema(
                module_name = module.name,
                label       = module.label,
                can_read    = perm.can_read,
                can_create  = perm.can_create,
                can_update  = perm.can_update,
                can_delete  = perm.can_delete,
                source      = source
            ))

        return UserPermissionsResponseSchema(
            id_user     = user.id_user,
            username    = user.username,
            role_name   = role.name,
            role_type   = role.permission_type.value,
            permissions = permissions
        )

    def save_user_permissions(
        self,
        user_id: int,
        payload: SaveUserPermissionsSchema,
        admin_id: int
    ) -> UserPermissionsResponseSchema:
        """
        Salva la matrice permessi di un utente.
        Verifica la password admin prima di procedere.
        """

        # Verifica password admin
        admin = self._user_repo.get_by_id_or_raise(admin_id)
        if not bcrypt_context.verify(payload.admin_password, admin.password):
            raise AuthenticationException(
                "Password admin non corretta"
            )

        # Verifica che l'utente esista
        self._user_repo.get_by_id_or_raise(user_id)

        # Salva ogni riga della matrice
        for perm in payload.permissions:

            module = self._db.query(AppModule).filter(
                AppModule.name == perm.module_name
            ).first()

            if not module:
                raise NotFoundException("AppModule", perm.module_name)

            self._permission_repo.save_user_permissions(
                user_id    = user_id,
                module_id  = module.id_module,
                can_read   = perm.can_read,
                can_create = perm.can_create,
                can_update = perm.can_update,
                can_delete = perm.can_delete,
                created_by = admin_id
            )

        return self.get_user_permissions(user_id)

    # ──────────────────────────────────────────────────────
    # MATRICE RUOLO
    # ──────────────────────────────────────────────────────

    def get_role_permissions(
        self,
        role_id: int
    ) -> RolePermissionsResponseSchema:
        """
        Costruisce la matrice completa dei permessi di un ruolo.

        Per ruoli full_crud restituisce tutti i flag a True
        perché il bypass avviene a livello di check_permission.
        """
        role = self._role_repo.get_by_id_or_raise(role_id)

        # Carica tutti i moduli attivi
        modules = self._db.query(AppModule).filter(
            AppModule.is_active == True
        ).order_by(AppModule.sort_order).all()

        # ── Caso speciale: ruoli full_crud → tutti i flag True ──
        if role.permission_type.value == PermissionType.full_crud.value:
            permissions = [
                ModulePermissionResponseSchema(
                    module_name = module.name,
                    label       = module.label,
                    can_read    = True,
                    can_create  = True,
                    can_update  = True,
                    can_delete  = True,
                    source      = 'full_crud'
                )
                for module in modules
            ]
            return RolePermissionsResponseSchema(
                id_role     = role.id_role,
                role_name   = role.name,
                role_type   = role.permission_type.value,
                permissions = permissions
            )

        # ── Logica standard per ruoli custom ──
        role_perms = self._permission_repo.get_all_role_permissions(role_id)
        role_map = {p.id_module: p for p in role_perms}

        permissions = []
        for module in modules:
            if module.id_module in role_map:
                perm = role_map[module.id_module]
                permissions.append(ModulePermissionResponseSchema(
                    module_name = module.name,
                    label       = module.label,
                    can_read    = perm.can_read,
                    can_create  = perm.can_create,
                    can_update  = perm.can_update,
                    can_delete  = perm.can_delete,
                    source      = 'role'
                ))
            else:
                permissions.append(ModulePermissionResponseSchema(
                    module_name = module.name,
                    label       = module.label,
                    can_read    = False,
                    can_create  = False,
                    can_update  = False,
                    can_delete  = False,
                    source      = 'none'
                ))

        return RolePermissionsResponseSchema(
            id_role     = role.id_role,
            role_name   = role.name,
            role_type   = role.permission_type.value,
            permissions = permissions
        )

    def save_role_permissions(
        self,
        role_id: int,
        payload: SaveRolePermissionsSchema
    ) -> RolePermissionsResponseSchema:
        """
        Salva la matrice permessi di un ruolo.
        Bloccato per ruoli is_system=True.
        """
        role = self._role_repo.get_by_id_or_raise(role_id)

        if role.is_system:
            raise BusinessRuleException(
                "Non puoi modificare i permessi di un ruolo di sistema",
                details={"role_id": role_id}
            )

        for perm in payload.permissions:
            module = self._db.query(AppModule).filter(
                AppModule.name == perm.module_name
            ).first()

            if not module:
                raise NotFoundException("AppModule", perm.module_name)

            self._permission_repo.save_role_permissions(
                role_id    = role_id,
                module_id  = module.id_module,
                can_read   = perm.can_read,
                can_create = perm.can_create,
                can_update = perm.can_update,
                can_delete = perm.can_delete
            )

        return self.get_role_permissions(role_id)

    # ──────────────────────────────────────────────────────
    # METODO PRIVATO DI SUPPORTO
    # ──────────────────────────────────────────────────────

    def _get_flag(self, perm, action: str) -> bool:
        """
        Mappa l'azione al flag booleano corrispondente.
        """
        action_map = {
            'read':   perm.can_read,
            'create': perm.can_create,
            'update': perm.can_update,
            'delete': perm.can_delete,
        }
        return action_map.get(action, False)

    async def validate_business_rules(self, data: Any) -> None:
        pass