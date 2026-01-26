"""Runtime helpers to access the event system singletons."""

from __future__ import annotations

import asyncio
from typing import Optional

from .config.config_loader import EventConfigLoader
from .core.event import Event
from .core.event_bus import EventBus
from .marketplace.marketplace_client import MarketplaceClient
from .plugin_manager import PluginManager
import logging

_event_bus: Optional[EventBus] = None
_plugin_manager: Optional[PluginManager] = None
_config_loader: Optional[EventConfigLoader] = None
_marketplace_client: Optional[MarketplaceClient] = None


def set_event_bus(event_bus: EventBus) -> None:
    global _event_bus
    _event_bus = event_bus


def get_event_bus() -> EventBus:
    if _event_bus is None:
        raise RuntimeError("EventBus has not been initialised")
    return _event_bus


def set_plugin_manager(manager: PluginManager) -> None:
    global _plugin_manager
    _plugin_manager = manager


def get_plugin_manager() -> PluginManager:
    if _plugin_manager is None:
        raise RuntimeError("PluginManager has not been initialised")
    return _plugin_manager


def emit_event(event: Event) -> None:
    """Publish an event using the currently configured EventBus."""
    logger = logging.getLogger(__name__)
    logger.info(f"[RUNTIME] emit_event chiamato per evento: type={event.event_type}, data={event.data}")

    event_bus = get_event_bus()
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(event_bus.publish(event))
    except RuntimeError:
        asyncio.run(event_bus.publish(event))


def set_config_loader(loader: EventConfigLoader) -> None:
    global _config_loader
    _config_loader = loader


def get_config_loader() -> EventConfigLoader:
    if _config_loader is None:
        raise RuntimeError("Event configuration loader not initialised")
    return _config_loader


def set_marketplace_client(client: MarketplaceClient) -> None:
    global _marketplace_client
    _marketplace_client = client


def get_marketplace_client() -> MarketplaceClient:
    if _marketplace_client is None:
        raise RuntimeError("Marketplace client not initialised")
    return _marketplace_client

