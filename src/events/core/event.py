"""Definitions for events emitted by the platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Mapping, MutableMapping


class EventType(str, Enum):
    """Types of events supported by the system."""

    ORDER_STATUS_CHANGED = "order_status_changed"

    @classmethod
    def has_value(cls, value: str) -> bool:
        """Return True if the enum already defines the given value."""

        try:
            cls(value)
        except ValueError:
            return False
        return True


MetadataMapping = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Event:
    """Event data structure shared across the event system."""

    event_type: str
    data: Dict[str, Any]
    metadata: MetadataMapping = field(default_factory=dict)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        """Normalise metadata and ensure immutability friendly structures."""

        if not isinstance(self.metadata, dict):
            object.__setattr__(self, "metadata", dict(self.metadata))

        if "idempotency_key" not in self.metadata:
            object.__setattr__(
                self,
                "metadata",
                {**self.metadata, "idempotency_key": self._generate_idempotency_key()},
            )

    @property
    def idempotency_key(self) -> str:
        """Convenience accessor for the idempotency key."""

        return str(self.metadata.get("idempotency_key", ""))

    def with_metadata(self, **updates: Any) -> "Event":
        """Return a copy of the event with updated metadata."""

        merged: MutableMapping[str, Any] = dict(self.metadata)
        merged.update(updates)
        return Event(
            event_type=self.event_type,
            data=self.data,
            metadata=dict(merged),
            timestamp=self.timestamp,
        )

    def _generate_idempotency_key(self) -> str:
        """Generate a deterministic idempotency key for the event."""

        return f"{self.event_type}:{int(self.timestamp.timestamp() * 1_000_000)}"

