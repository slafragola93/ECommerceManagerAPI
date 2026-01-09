"""Definitions for events emitted by the platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, MutableMapping


class EventType(str, Enum):
    """Types of events supported by the system."""

    # Eventi esistenti
    ORDER_STATUS_CHANGED = "order_status_changed"
    SHIPPING_STATUS_CHANGED = "shipping_status_changed"
    
    # ===== SHIPMENTS =====
    SHIPMENT_CREATED = "shipment_created"

    # ===== DOCUMENTI (OrderDocument + FiscalDocument unificati) =====
    # Distinguere tramite document_source ("order_document" o "fiscal_document")
    # e document_type ("preventivo", "ddt", "invoice", "credit_note")
    DOCUMENT_CREATED = "document_created"
    DOCUMENT_UPDATED = "document_updated"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_CONVERTED = "document_converted"  # preventivo -> order
    DOCUMENT_BULK_DELETED = "document_bulk_deleted"

    # ===== ORDINI =====
    ORDER_CREATED = "order_created"
    ORDER_UPDATED = "order_updated"
    ORDER_DELETED = "order_deleted"

    # ===== CUSTOMER =====
    CUSTOMER_CREATED = "customer_created"
    CUSTOMER_UPDATED = "customer_updated"
    CUSTOMER_DELETED = "customer_deleted"

    # ===== PRODUCT =====
    PRODUCT_CREATED = "product_created"
    PRODUCT_UPDATED = "product_updated"

    # ===== ADDRESS =====
    ADDRESS_CREATED = "address_created"

    # ===== SYNC/IMPORT =====
    PRESTASHOP_SYNC_STARTED = "prestashop_sync_started"
    PRESTASHOP_SYNC_COMPLETED = "prestashop_sync_completed"
    PRESTASHOP_SYNC_FAILED = "prestashop_sync_failed"
    PRODUCT_IMPORTED = "product_imported"
    ORDER_IMPORTED = "order_imported"
    CUSTOMER_IMPORTED = "customer_imported"

    # ===== PLUGIN LIFECYCLE =====
    PLUGIN_INSTALLED = "plugin_installed"
    PLUGIN_UNINSTALLED = "plugin_uninstalled"
    PLUGIN_ENABLED = "plugin_enabled"
    PLUGIN_DISABLED = "plugin_disabled"
    PLUGIN_LOADED = "plugin_loaded"
    PLUGIN_UNLOADED = "plugin_unloaded"

    @classmethod
    def has_value(cls, value: str) -> bool:
        """Return True if the enum already defines the given value."""

        try:
            cls(value)
        except ValueError:
            return False
        return True
    
    @classmethod
    def get_all_events(cls) -> List[Dict[str, str]]:
        """Restituisce lista di tutti gli eventi disponibili nell'applicazione."""
        return [
            {"value": event.value, "name": event.name}
            for event in cls
        ]


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