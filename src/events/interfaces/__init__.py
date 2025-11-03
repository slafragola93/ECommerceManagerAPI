"""Interfaces for the event plugin system."""

from .event_handler_plugin import EventHandlerPlugin, PluginMetadata
from .base_event_handler import BaseEventHandler

__all__ = ["EventHandlerPlugin", "PluginMetadata", "BaseEventHandler"]

