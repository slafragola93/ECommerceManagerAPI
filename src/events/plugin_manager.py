"""Gestore di alto livello per orchestrare il ciclo di vita dei plugin e le sottoscrizioni."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from types import ModuleType
from typing import Awaitable, Callable, Dict, List, Optional, Sequence

from .config import EventConfig, EventConfigLoader
from .config.config_schema import PluginSettings
from .core.event import Event, EventType
from .core.event_bus import EventBus
from .interfaces import BaseEventHandler, EventHandlerPlugin
from .plugin_loader import PluginDescriptor, PluginLoader

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LoadedPlugin:
    name: str
    module: ModuleType
    instance: EventHandlerPlugin
    handlers: Dict[str, BaseEventHandler]
    descriptor: PluginDescriptor
    enabled: bool = True


@dataclass(slots=True)
class RegisteredHandler:
    name: str
    plugin_name: str
    handler: BaseEventHandler


class PluginManager:
    """Manage plugin lifecycle and event subscriptions."""

    def __init__(
        self,
        event_bus: EventBus,
        config_loader: EventConfigLoader,
        plugin_loader: PluginLoader,
    ) -> None:
        self._event_bus = event_bus
        self._config_loader = config_loader
        self._plugin_loader = plugin_loader
        self._lock = asyncio.Lock()

        self._config: Optional[EventConfig] = None
        self._loaded_plugins: Dict[str, LoadedPlugin] = {}
        self._handlers: Dict[str, RegisteredHandler] = {}
        self._event_callbacks: Dict[str, Callable[[Event], Awaitable[None]]] = {}

    async def initialise(self) -> EventConfig:
        return await self.reload()

    async def reload(self) -> EventConfig:
        async with self._lock:
            return await self._reload_internal()

    async def _reload_internal(self) -> EventConfig:
        """Internal reload without lock acquisition - must be called while lock is held."""
        config = self._config_loader.refresh()
        self._config = config

        self._plugin_loader.set_directories(config.plugin_directories)
        discovered = self._plugin_loader.discover()

        await self._reconcile_plugins(discovered, config)
        await self._rebuild_event_subscriptions(config)

        return config.model_copy(deep=True)

    async def enable_plugin(self, plugin_name: str) -> EventConfig:
        async with self._lock:
            config = self._ensure_config()
            settings = config.plugins.get(plugin_name, PluginSettings())
            settings.enabled = True
            config.plugins[plugin_name] = settings
            self._config_loader.save(config)
            return await self._reload_internal()

    async def disable_plugin(self, plugin_name: str) -> EventConfig:
        async with self._lock:
            config = self._ensure_config()
            settings = config.plugins.get(plugin_name, PluginSettings())
            settings.enabled = False
            config.plugins[plugin_name] = settings
            self._config_loader.save(config)
            return await self._reload_internal()

    async def get_status(self) -> Dict[str, Dict[str, object]]:
        async with self._lock:
            config = self._ensure_config()
            result: Dict[str, Dict[str, object]] = {}
            for name, plugin in self._loaded_plugins.items():
                result[name] = {
                    "enabled": plugin.enabled,
                    "handlers": list(plugin.handlers.keys()),
                    "source": plugin.descriptor.source,
                    "config": config.plugins.get(name, PluginSettings()).model_dump(),
                }
            return result

    def get_loaded_plugins(self) -> Dict[str, LoadedPlugin]:
        return dict(self._loaded_plugins)

    async def _reconcile_plugins(
        self,
        discovered: Dict[str, PluginDescriptor],
        config: EventConfig,
    ) -> None:
        removed = set(self._loaded_plugins) - set(discovered)
        for name in removed:
            await self._unload_plugin(name)

        for name, descriptor in discovered.items():
            await self._load_or_refresh_plugin(name, descriptor, config)

    async def _load_or_refresh_plugin(
        self,
        name: str,
        descriptor: PluginDescriptor,
        config: EventConfig,
    ) -> None:
        existing = self._loaded_plugins.get(name)
        plugin_enabled = self._is_plugin_enabled(name, config)

        if existing and existing.descriptor == descriptor:
            if existing.enabled != plugin_enabled:
                if plugin_enabled:
                    await existing.instance.on_load()
                else:
                    await existing.instance.on_unload()
                existing.enabled = plugin_enabled
            return

        if existing:
            await self._unload_plugin(name)

        module = self._plugin_loader.load_module(descriptor)
        instance = self._create_plugin_instance(module)
        handlers = self._collect_handlers(instance)

        loaded = LoadedPlugin(
            name=name,
            module=module,
            instance=instance,
            handlers=handlers,
            descriptor=descriptor,
            enabled=plugin_enabled,
        )
        self._loaded_plugins[name] = loaded

        for handler_name, handler in handlers.items():
            self._handlers[handler_name] = RegisteredHandler(
                name=handler_name,
                plugin_name=name,
                handler=handler,
            )

        if plugin_enabled:
            await instance.on_load()

    async def _unload_plugin(self, name: str) -> None:
        plugin = self._loaded_plugins.pop(name, None)
        if not plugin:
            return

        try:
            await plugin.instance.on_unload()
        finally:
            for handler_name in list(plugin.handlers):
                self._handlers.pop(handler_name, None)

    async def _rebuild_event_subscriptions(self, config: EventConfig) -> None:
        for event_type, callback in self._event_callbacks.items():
            try:
                await self._event_bus.unsubscribe(event_type, callback)
            except Exception:
                logger.exception("Failed to unsubscribe callback for event '%s'", event_type)

        self._event_callbacks.clear()

        event_types: set[str] = {
            *config.routes.keys(),
            *(event_type.value for event_type in EventType),
        }

        for event_type in event_types:
            event_type_key = str(event_type)

            async def _callback(event: Event, *, expected_type=event_type_key) -> None:
                if event.event_type != expected_type:
                    return
                await self._handle_event(event)

            await self._event_bus.subscribe(event_type_key, _callback)
            self._event_callbacks[event_type_key] = _callback

    async def _handle_event(self, event: Event) -> None:
        handlers = self._resolve_handlers(event)
        
        if not handlers:
            return

        tasks = [handler(event) for handler in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for handler, result in zip(handlers, results):
            if isinstance(result, Exception):
                logger.exception(
                    "Handler %s failed for event '%s'", handler.name, event.event_type, exc_info=result
                )


    def _resolve_handlers(self, event: Event) -> List[BaseEventHandler]:
        config = self._ensure_config()
        state_id = event.data.get("new_state_id") or event.data.get("state_id")

        routed = config.get_handlers_for_route(event.event_type, state_id)
        if routed:
            candidate_names: Sequence[str] = routed
        else:
            candidate_names = list(self._handlers.keys())

        resolved: List[BaseEventHandler] = []
        for name in candidate_names:
            registered = self._handlers.get(name)
            if not registered:
                continue

            plugin = self._loaded_plugins.get(registered.plugin_name)
            if not plugin:
                continue
            if not plugin.enabled:
                continue

            if not config.is_handler_enabled(name):
                continue

            can_handle_result = registered.handler.can_handle(event)
            if not can_handle_result:
                continue

            resolved.append(registered.handler)

        return resolved

    def _create_plugin_instance(self, module: ModuleType) -> EventHandlerPlugin:
        for attr in ("get_plugin", "create_plugin", "plugin_factory"):
            factory = getattr(module, attr, None)
            if callable(factory):
                plugin = factory()
                if isinstance(plugin, EventHandlerPlugin):
                    return plugin
                raise TypeError(
                    f"Factory '{attr}' did not return an EventHandlerPlugin instance"
                )

        for attr in ("PLUGIN_CLASS", "Plugin", "PLUGIN"):
            plugin_cls = getattr(module, attr, None)
            if isinstance(plugin_cls, type) and issubclass(plugin_cls, EventHandlerPlugin):
                return plugin_cls()

        raise ValueError("Plugin module does not expose a recognised factory or class")

    def _collect_handlers(self, plugin: EventHandlerPlugin) -> Dict[str, BaseEventHandler]:
        handlers = plugin.get_handlers()
        if not isinstance(handlers, list):
            raise TypeError("Plugin get_handlers() must return a list of handlers")

        collected: Dict[str, BaseEventHandler] = {}
        for handler in handlers:
            if not isinstance(handler, BaseEventHandler):
                raise TypeError("Handler must inherit from BaseEventHandler")

            name = handler.name
            if name in collected or name in self._handlers:
                logger.warning("Duplicate handler name '%s' detected; skipping", name)
                continue

            collected[name] = handler

        return collected

    def _is_plugin_enabled(self, plugin_name: str, config: EventConfig) -> bool:
        settings = config.plugins.get(plugin_name)
        if settings and settings.enabled is not None:
            return settings.enabled
        return True

    def _ensure_config(self) -> EventConfig:
        if not self._config:
            self._config = self._config_loader.load(use_cache=True)
        return self._config

