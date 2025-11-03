"""Pydantic models describing the event configuration structure."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MarketplaceSettings(BaseModel):
    """Configuration for the external marketplace integration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    base_url: str = Field(default="https://marketplace.example.com/api")
    api_key: str = Field(default="")
    verify_signature: bool = False
    download_timeout_seconds: int = Field(default=30, ge=1)


class PluginSettings(BaseModel):
    """Configuration for a single plugin."""

    model_config = ConfigDict(extra="allow")

    enabled: Optional[bool] = None


class EventConfig(BaseModel):
    """Root configuration model for the event system."""

    model_config = ConfigDict(extra="forbid")

    plugin_directories: List[str] = Field(default_factory=list)
    enabled_handlers: List[str] = Field(default_factory=list)
    disabled_handlers: List[str] = Field(default_factory=list)
    routes: Dict[str, Dict[str, List[str]]] = Field(default_factory=dict)
    plugins: Dict[str, PluginSettings] = Field(default_factory=dict)
    marketplace: MarketplaceSettings = Field(default_factory=MarketplaceSettings)

    @field_validator("plugin_directories", mode="after")
    @classmethod
    def normalise_directories(cls, value: Sequence[str]) -> List[str]:
        return [str(Path(directory)) for directory in value if str(directory).strip()]

    @field_validator("enabled_handlers", "disabled_handlers", mode="after")
    @classmethod
    def normalise_handler_lists(cls, value: Sequence[str]) -> List[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for handler in value:
            handler_name = handler.strip()
            if handler_name and handler_name not in seen:
                seen.add(handler_name)
                ordered.append(handler_name)
        return ordered

    def is_handler_enabled(self, handler_name: str) -> bool:
        name = handler_name.strip()
        if not name:
            return False

        plugin_cfg = self.plugins.get(name)
        if plugin_cfg and plugin_cfg.enabled is not None:
            return plugin_cfg.enabled

        if name in self.disabled_handlers:
            return False

        if self.enabled_handlers:
            return name in self.enabled_handlers

        return True

    def get_handlers_for_route(
        self, event_type: str, state_id: Optional[int | str]
    ) -> List[str]:
        routing = self.routes.get(event_type, {})
        if state_id is None:
            return [handler for handlers in routing.values() for handler in handlers]

        key = str(state_id)
        handlers = routing.get(key, [])
        wildcard_handlers = routing.get("*", [])
        return list(dict.fromkeys([*handlers, *wildcard_handlers]))

