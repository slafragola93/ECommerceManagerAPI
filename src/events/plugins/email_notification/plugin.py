"""Email notification plugin implementation."""

from __future__ import annotations

from typing import Dict, List, Optional

from src.events.interfaces import BaseEventHandler, EventHandlerPlugin
from src.events.plugins.email_notification.handlers import EmailNotificationHandler


class EmailNotificationPlugin(EventHandlerPlugin):
    """Example plugin that exposes a single email notification handler."""

    def __init__(self, *, settings: Optional[Dict[str, str]] = None) -> None:
        super().__init__(name="EmailNotificationPlugin")
        self._settings = settings or {}
        self._handlers: List[BaseEventHandler] = [EmailNotificationHandler()]

    def get_handlers(self) -> List[BaseEventHandler]:
        return self._handlers

    def get_metadata(self) -> Dict[str, str]:
        return {
            "version": "1.0.0",
            "category": "notifications",
            **self._settings,
        }


def get_plugin() -> EventHandlerPlugin:
    return EmailNotificationPlugin()


PLUGIN_CLASS = EmailNotificationPlugin

