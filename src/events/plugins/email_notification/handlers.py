"""Example handler that simulates sending an email notification."""

from __future__ import annotations

import logging
from typing import Any, Dict

from src.events.core.event import Event, EventType
from src.events.interfaces import BaseEventHandler

logger = logging.getLogger(__name__)


class EmailNotificationHandler(BaseEventHandler):
    """Simple handler that logs an email notification message."""

    def __init__(self, *, name: str = "email_notification_handler") -> None:
        super().__init__(name=name)

    def can_handle(self, event: Event) -> bool:
        return event.event_type == EventType.ORDER_STATUS_CHANGED.value

    async def handle(self, event: Event) -> None:
        payload = _format_payload(event.data)
        logger.info(
            "Email notification sent for order %(order_id)s (state %(state)s)",
            payload,
            extra={"event_metadata": event.metadata},
        )


def _format_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    order_id = data.get("order_id", "unknown")
    new_state = data.get("new_state_id", "")
    old_state = data.get("old_state_id", "")
    return {
        "order_id": order_id,
        "state": str(new_state),
        "previous_state": str(old_state),
    }

