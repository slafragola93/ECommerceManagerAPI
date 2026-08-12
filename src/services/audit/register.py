"""Register core audit handlers on the EventBus (not via PluginManager)."""

from __future__ import annotations

import logging

from src.events.core.event_bus import EventBus
from src.services.audit.audit_level_map import subscribed_event_types
from src.services.audit.audit_log_handler import handle_audit_event_safe

logger = logging.getLogger(__name__)


async def register_audit_handlers(event_bus: EventBus) -> None:
    """Subscribe the audit handler to all curated EventType values."""
    for event_type in subscribed_event_types():
        await event_bus.subscribe(event_type, handle_audit_event_safe)
    logger.info(
        "Audit log handler subscribed to %s event types",
        len(subscribed_event_types()),
    )
