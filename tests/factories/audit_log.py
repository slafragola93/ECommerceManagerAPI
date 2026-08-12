"""Factory helpers for AuditLog tests."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.models.audit_log import AuditLog


def create_audit_log_data(
    *,
    actor_id: Optional[int] = 1,
    actor_username: str = "admin",
    actor_role: str = "ADMIN",
    action: str = "order.create",
    resource_type: str = "order",
    resource_id: str = "42",
    changes: Optional[Dict[str, Any]] = None,
    level: str = "standard",
    ip_address: Optional[str] = "127.0.0.1",
    request_id: Optional[str] = "00000000-0000-0000-0000-000000000001",
    status: str = "success",
    timestamp: Optional[datetime] = None,
) -> Dict[str, Any]:
    return {
        "timestamp": timestamp or datetime.now(timezone.utc),
        "actor_id": actor_id,
        "actor_username": actor_username,
        "actor_role": actor_role,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "changes": changes,
        "level": level,
        "ip_address": ip_address,
        "request_id": request_id,
        "status": status,
    }


def create_audit_log(**kwargs) -> AuditLog:
    return AuditLog(**create_audit_log_data(**kwargs))
