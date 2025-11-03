"""Custom exceptions for the event system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Sequence

from .event import Event


class EventBusError(Exception):
    """Base exception for the event system."""


@dataclass(slots=True)
class HandlerFailure:
    """Details about a handler failure."""

    handler: Callable[[Event], Any]
    event: Event
    exception: Exception

    def __str__(self) -> str:  # pragma: no cover - repr helper
        return f"Handler {self.handler} failed for event {self.event}: {self.exception}"


class HandlerExecutionError(EventBusError):
    """Exception raised when one or more handlers fail to execute."""

    def __init__(self, failures: Sequence[HandlerFailure]):
        self.failures: List[HandlerFailure] = list(failures)
        message = ", ".join(str(failure) for failure in self.failures)
        super().__init__(message)

    @classmethod
    def from_single(
        cls, handler: Callable[[Event], Any], event: Event, original_exc: Exception
    ) -> "HandlerExecutionError":
        return cls([HandlerFailure(handler=handler, event=event, exception=original_exc)])

    @classmethod
    def merge(cls, failures: Iterable[HandlerFailure]) -> "HandlerExecutionError":
        return cls(list(failures))

