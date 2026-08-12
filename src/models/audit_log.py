"""SQLAlchemy model for append-only audit_logs table."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, Integer, JSON, String

from src.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(Base):
    """
    Riga di audit append-only.

    Nessun UPDATE/DELETE previsto a livello applicativo: i log sopravvivono
    a cancellazioni utente grazie agli snapshot actor_username / actor_role.
    """

    __tablename__ = "audit_logs"

    id_audit_log = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=_utc_now, index=True)
    actor_id = Column(Integer, nullable=True, index=True)
    actor_username = Column(String(100), nullable=False, default="system")
    actor_role = Column(String(100), nullable=False, default="")
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False, index=True)
    resource_id = Column(String(100), nullable=True)
    changes = Column(JSON, nullable=True)
    level = Column(String(20), nullable=False, default="standard", index=True)
    ip_address = Column(String(45), nullable=True)
    request_id = Column(String(36), nullable=True)
    status = Column(String(20), nullable=False, default="success")

    __table_args__ = (
        Index("ix_audit_logs_timestamp_actor", "timestamp", "actor_id"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_level_timestamp", "level", "timestamp"),
    )
