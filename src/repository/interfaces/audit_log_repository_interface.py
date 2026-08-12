"""Interface for AuditLog repository."""

from abc import abstractmethod
from typing import List

from src.core.interfaces import IRepository
from src.models.audit_log import AuditLog


class IAuditLogRepository(IRepository[AuditLog, int]):
    """Repository append-only: create + query, no update/delete API."""

    @abstractmethod
    def get_all(self, **filters) -> List[AuditLog]:
        """Lista filtrata e paginata."""
        pass

    @abstractmethod
    def get_count(self, **filters) -> int:
        """Conteggio con gli stessi filtri di get_all (senza paginazione)."""
        pass
