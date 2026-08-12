"""Interface for AuditLog service (read-only)."""

from abc import abstractmethod
from typing import List

from src.core.interfaces import IBaseService
from src.models.audit_log import AuditLog


class IAuditLogService(IBaseService):
    """Service di sola lettura per audit logs."""

    @abstractmethod
    async def get_audit_logs(self, page: int = 1, limit: int = 10, **filters) -> List[AuditLog]:
        pass

    @abstractmethod
    async def get_audit_logs_count(self, **filters) -> int:
        pass

    @abstractmethod
    async def get_audit_log(self, id_audit_log: int) -> AuditLog:
        pass
