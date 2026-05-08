"""
Role Service rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional, Any
from src.services.interfaces.role_service_interface import IRoleService
from src.repository.interfaces.role_repository_interface import IRoleRepository
from src.schemas.role_schema import RoleSchema, RoleResponseSchema
from src.models.role import Role, PermissionType
from src.core.exceptions import (
    ValidationException,
    NotFoundException,
    BusinessRuleException,
    ExceptionFactory,
    ErrorCode
)


class RoleService(IRoleService):
    """Role Service rifattorizzato seguendo SRP, OCP, LSP, ISP, DIP"""

    def __init__(self, role_repository: IRoleRepository):
        self._role_repository = role_repository

    async def create_role(self, role_data: RoleSchema) -> Role:
        """Crea un nuovo ruolo con validazioni business"""

        # Business Rule 1: Nome deve essere unico
        if hasattr(role_data, 'name') and role_data.name:
            existing_role = self._role_repository.get_by_name(role_data.name)
            if existing_role:
                raise BusinessRuleException(
                    f"Esiste già un ruolo con nome '{role_data.name}'",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": role_data.name}
                )

        # Business Rule 2: full_crud è riservato ai ruoli di sistema
        # Solo i ruoli creati via seed possono avere is_system=True + full_crud
        # Via API non si può creare un ruolo con permission_type='full_crud'
        if self._is_full_crud(role_data):
            raise BusinessRuleException(
                "Il tipo 'full_crud' è riservato ai ruoli di sistema. "
                "I nuovi ruoli devono avere permission_type='custom'.",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"permission_type": "full_crud"}
            )

        # Crea il ruolo (escludendo eventuali campi gestiti dal backend)
        try:
            payload = role_data.model_dump(exclude={"is_system"})
            role = Role(**payload)
            # Forza is_system=False — solo il seed può creare ruoli di sistema
            role.is_system = False
            role = self._role_repository.create(role)
            return role
        except BusinessRuleException:
            raise
        except Exception as e:
            raise ValidationException(f"Errore nella creazione del ruolo: {str(e)}")

    async def update_role(self, role_id: int, role_data: RoleSchema) -> Role:
        """Aggiorna un ruolo esistente"""

        # Verifica esistenza
        role = self._role_repository.get_by_id_or_raise(role_id)

        # Business Rule: i ruoli di sistema NON possono essere modificati via API
        if role.is_system:
            raise BusinessRuleException(
                "Non puoi modificare un ruolo di sistema",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"role_id": role_id, "name": role.name}
            )

        # Business Rule: Se nome cambia, deve essere unico
        if hasattr(role_data, 'name') and role_data.name != role.name:
            existing = self._role_repository.get_by_name(role_data.name)
            if existing and existing.id_role != role_id:
                raise BusinessRuleException(
                    f"Esiste già un ruolo con nome '{role_data.name}'",
                    ErrorCode.BUSINESS_RULE_VIOLATION,
                    {"name": role_data.name}
                )

        # Business Rule: full_crud è riservato ai ruoli di sistema
        if self._is_full_crud(role_data):
            raise BusinessRuleException(
                "Solo i ruoli di sistema possono avere permission_type='full_crud'",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"permission_type": "full_crud"}
            )

        # Aggiorna il ruolo (escludendo i campi gestiti dal backend)
        try:
            skip_fields = {"is_system"}
            for field_name, value in role_data.model_dump(exclude_unset=True).items():
                if field_name in skip_fields:
                    continue
                if hasattr(role, field_name) and value is not None:
                    setattr(role, field_name, value)

            updated_role = self._role_repository.update(role)
            return updated_role
        except BusinessRuleException:
            raise
        except Exception as e:
            raise ValidationException(f"Errore nell'aggiornamento del ruolo: {str(e)}")

    async def get_role(self, role_id: int) -> Role:
        """Ottiene un ruolo per ID"""
        role = self._role_repository.get_by_id_or_raise(role_id)
        return role

    async def get_roles(self, page: int = 1, limit: int = 10, **filters) -> List[Role]:
        """Ottiene la lista dei ruoli con filtri"""
        try:
            if page < 1:
                page = 1
            if limit < 1:
                limit = 10

            filters['page'] = page
            filters['limit'] = limit

            roles = self._role_repository.get_all(**filters)
            return roles
        except Exception as e:
            raise ValidationException(f"Errore nel recupero dei ruoli: {str(e)}")

    async def delete_role(self, role_id: int) -> bool:
        """Elimina un ruolo"""

        # Verifica esistenza
        role = self._role_repository.get_by_id_or_raise(role_id)

        # Business Rule: i ruoli di sistema NON possono essere eliminati
        if role.is_system:
            raise BusinessRuleException(
                "Non puoi eliminare un ruolo di sistema",
                ErrorCode.BUSINESS_RULE_VIOLATION,
                {"role_id": role_id, "name": role.name}
            )

        try:
            return self._role_repository.delete(role_id)
        except BusinessRuleException:
            raise
        except Exception as e:
            raise ValidationException(f"Errore nell'eliminazione del ruolo: {str(e)}")

    async def get_roles_count(self, **filters) -> int:
        """Ottiene il numero totale di ruoli con filtri"""
        try:
            return self._role_repository.get_count(**filters)
        except Exception as e:
            raise ValidationException(f"Errore nel conteggio dei ruoli: {str(e)}")

    async def validate_business_rules(self, data: Any) -> None:
        """Valida le regole business per Role"""
        pass

    # ──────────────────────────────────────────────────────
    # METODI PRIVATI DI SUPPORTO
    # ──────────────────────────────────────────────────────

    def _is_full_crud(self, role_data: RoleSchema) -> bool:
        """
        Verifica se il payload tenta di impostare permission_type='full_crud'.
        Compatibile sia con valori Enum che con stringhe (use_enum_values=True).
        """
        pt = getattr(role_data, "permission_type", None)
        if pt is None:
            return False

        # Pydantic con use_enum_values=True restituisce stringhe
        if isinstance(pt, str):
            return pt == PermissionType.full_crud.value

        # Caso fallback: se è ancora un Enum
        return pt == PermissionType.full_crud