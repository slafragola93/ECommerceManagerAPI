"""Base abstractions for event handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..core.event import Event


class BaseEventHandler(ABC):
    """Base class for all event handlers."""

    def __init__(self, *, name: Optional[str] = None) -> None:
        self._name = name or self.__class__.__name__

    @property
    def name(self) -> str:
        return self._name

    def can_handle(self, event: Event) -> bool:
        return True

    async def __call__(self, event: Event) -> None:
        await self.handle(event)

    @abstractmethod
    async def handle(self, event: Event) -> None:
        raise NotImplementedError

