"""AuditLog repository — append-only queries."""

from typing import List

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.core.base_repository import BaseRepository
from src.core.exceptions import InfrastructureException
from src.models.audit_log import AuditLog
from src.repository.interfaces.audit_log_repository_interface import IAuditLogRepository
from src.services import QueryUtils


class AuditLogRepository(BaseRepository[AuditLog, int], IAuditLogRepository):
    """Data access for audit_logs. Update/delete non esposti a livello applicativo."""

    def __init__(self, session: Session):
        super().__init__(session, AuditLog)

    def _apply_audit_filters(self, query, filters: dict):
        actor_id = filters.get("actor_id")
        if actor_id is not None:
            # filter_by_id accetta CSV/list; normalizziamo l'int singolo dalla query
            query = QueryUtils.filter_by_id(
                query,
                AuditLog,
                "actor_id",
                actor_id if isinstance(actor_id, (list, tuple, str)) else [actor_id],
            )

        query = QueryUtils.filter_by_string(
            query, AuditLog, "resource_type", filters.get("resource_type")
        )
        resource_id = filters.get("resource_id")
        if resource_id is not None and resource_id != "":
            query = query.filter(AuditLog.resource_id == str(resource_id))

        query = QueryUtils.filter_by_string(
            query, AuditLog, "action", filters.get("action")
        )
        level = filters.get("level")
        if level:
            query = query.filter(AuditLog.level == level)

        query = QueryUtils.filter_by_date(
            query,
            AuditLog,
            "timestamp",
            filters.get("date_from"),
            filters.get("date_to"),
        )
        return query

    def get_all(self, **filters) -> List[AuditLog]:
        try:
            query = self._session.query(AuditLog).order_by(desc(AuditLog.timestamp))
            query = self._apply_audit_filters(query, filters)
            page = filters.get("page", 1)
            limit = filters.get("limit", 100)
            offset = self.get_offset(limit, page)
            return query.offset(offset).limit(limit).all()
        except Exception as e:
            raise InfrastructureException(
                f"Database error retrieving AuditLog list: {str(e)}"
            )

    def get_count(self, **filters) -> int:
        try:
            query = self._session.query(AuditLog)
            query = self._apply_audit_filters(query, filters)
            return query.count()
        except Exception as e:
            raise InfrastructureException(
                f"Database error counting AuditLog: {str(e)}"
            )

    def delete(self, id: int) -> bool:  # noqa: A003
        """Append-only: delete non consentito."""
        raise InfrastructureException("AuditLog is append-only; delete is not allowed")

    def update(self, entity) -> AuditLog:
        """Append-only: update non consentito."""
        raise InfrastructureException("AuditLog is append-only; update is not allowed")
