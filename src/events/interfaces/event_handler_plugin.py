"""Interface definition for event handler plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .base_event_handler import BaseEventHandler

PluginMetadata = Dict[str, Any]


class EventHandlerPlugin(ABC):
    """Interface every plugin must implement."""

    def __init__(self, *, name: Optional[str] = None) -> None:
        self._name = name or self.__class__.__name__

    @property
    def name(self) -> str:
        return self._name

    @abstractmethod
    def get_handlers(self) -> List[BaseEventHandler]:
        raise NotImplementedError

    def get_metadata(self) -> PluginMetadata:
        return {}

    async def on_load(self) -> None:
        return None

    async def on_unload(self) -> None:
        return None

