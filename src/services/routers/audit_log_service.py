"""
AuditLog service — read-only.

Visibilità: all-or-nothing tramite require_permission("audit", "read") nel router.
Nessuno scoping actor_id == current_user; nessuna redaction campi.
Sul modulo audit can_create/can_update/can_delete non sono usati (append-only).
"""

from typing import Any, List

from src.models.audit_log import AuditLog
from src.repository.interfaces.audit_log_repository_interface import IAuditLogRepository
from src.services.interfaces.audit_log_service_interface import IAuditLogService


class AuditLogService(IAuditLogService):
    def __init__(self, audit_log_repository: IAuditLogRepository = None):
        self._audit_log_repository = audit_log_repository

    async def validate_business_rules(self, data: Any) -> None:
        """Read-only service: nessuna regola di scrittura."""
        return None

    async def get_audit_logs(
        self, page: int = 1, limit: int = 10, **filters
    ) -> List[AuditLog]:
        if page < 1:
            page = 1
        if limit < 1:
            limit = 10
        filters["page"] = page
        filters["limit"] = limit
        return self._audit_log_repository.get_all(**filters)

    async def get_audit_logs_count(self, **filters) -> int:
        # Evita che page/limit influenzino il count
        filters.pop("page", None)
        filters.pop("limit", None)
        return self._audit_log_repository.get_count(**filters)

    async def get_audit_log(self, id_audit_log: int) -> AuditLog:
        return self._audit_log_repository.get_by_id_or_raise(id_audit_log)
