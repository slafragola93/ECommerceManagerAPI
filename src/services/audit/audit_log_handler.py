"""
Core EventBus subscriber that persists audit rows.

NOT registered as a plugin (no circuit breaker). Failures are logged and
never re-raised so they cannot break the originating request or other handlers.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from src.database import SessionLocal
from src.events.core.event import Event
from src.models.audit_log import AuditLog
from src.services.audit.audit_level_map import (
    extract_changes,
    extract_resource_id,
    get_mapping,
)

logger = logging.getLogger(__name__)


def _meta_str(metadata: dict, key: str, default: str = "") -> str:
    value = metadata.get(key)
    if value is None:
        return default
    return str(value)


def _meta_optional_int(metadata: dict, key: str) -> Optional[int]:
    value = metadata.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def handle_audit_event(event: Event) -> None:
    """Persist a single audit_logs row from an EventBus event."""
    mapping = get_mapping(event.event_type)
    if mapping is None:
        return

    action, resource_type, level = mapping
    metadata = dict(event.metadata or {})
    data = dict(event.data or {})

    actor_id = _meta_optional_int(metadata, "actor_id")
    actor_username = _meta_str(metadata, "actor_username", "system") or "system"
    actor_role = _meta_str(metadata, "actor_role", "")
    request_id = metadata.get("request_id")
    ip_address = metadata.get("ip_address")

    if (
        data.get("status") == "failure"
        or metadata.get("status") == "failure"
        or event.event_type.endswith("_failed")
        or "login_failed" in action
    ):
        status = "failure"
    else:
        status = "success"

    # Auth login failed may carry attempted username in data
    if actor_username == "system" and data.get("username"):
        actor_username = str(data["username"])

    ts = event.timestamp
    if ts is not None and ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    if ts is None:
        ts = datetime.now(timezone.utc)

    row = AuditLog(
        timestamp=ts,
        actor_id=actor_id,
        actor_username=actor_username,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=extract_resource_id(data),
        changes=extract_changes(data),
        level=level,
        ip_address=str(ip_address) if ip_address else None,
        request_id=str(request_id) if request_id else None,
        status=status,
    )

    db = SessionLocal()
    try:
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to persist audit log for event '%s' (action=%s)",
            event.event_type,
            action,
        )
    finally:
        db.close()


async def handle_audit_event_safe(event: Event) -> None:
    """Wrapper that never propagates exceptions to EventBus gather."""
    try:
        await handle_audit_event(event)
    except Exception:
        logger.exception(
            "Unexpected error in audit handler for event '%s'", event.event_type
        )
