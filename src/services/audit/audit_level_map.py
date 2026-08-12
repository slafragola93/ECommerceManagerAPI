"""
Mapping EventType → (action, resource_type, level) for audit persistence.

Levels:
- standard: CUD business entities
- sensitive: fiscal/sync/export/PDF
- security: auth and role changes
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from src.events.core.event import EventType

# action, resource_type, level
AuditMapping = Tuple[str, str, str]

EVENT_AUDIT_MAP: Dict[str, AuditMapping] = {
    # Orders
    EventType.ORDER_CREATED.value: ("order.create", "order", "standard"),
    EventType.ORDER_UPDATED.value: ("order.update", "order", "standard"),
    EventType.ORDER_DELETED.value: ("order.delete", "order", "standard"),
    EventType.ORDER_STATUS_CHANGED.value: ("order.status_change", "order", "standard"),
    EventType.ORDER_VIES_EXEMPTION_APPLIED.value: (
        "order.vies_exemption",
        "order",
        "sensitive",
    ),
    EventType.ORDER_VIES_STATUS_CHANGED.value: (
        "order.vies_status",
        "order",
        "sensitive",
    ),
    EventType.ORDER_TRACKING_UPDATED.value: ("order.tracking_update", "order", "standard"),
    # Customers / products / addresses
    EventType.CUSTOMER_CREATED.value: ("customer.create", "customer", "standard"),
    EventType.CUSTOMER_UPDATED.value: ("customer.update", "customer", "standard"),
    EventType.CUSTOMER_DELETED.value: ("customer.delete", "customer", "standard"),
    EventType.PRODUCT_CREATED.value: ("product.create", "product", "standard"),
    EventType.PRODUCT_UPDATED.value: ("product.update", "product", "standard"),
    EventType.ADDRESS_CREATED.value: ("address.create", "address", "standard"),
    # Shipments
    EventType.SHIPMENT_CREATED.value: ("shipment.create", "shipment", "standard"),
    EventType.SHIPPING_STATUS_CHANGED.value: (
        "shipment.status_change",
        "shipment",
        "standard",
    ),
    # Documents (preventivi/DDT/fiscal generic)
    EventType.DOCUMENT_CREATED.value: ("document.create", "document", "standard"),
    EventType.DOCUMENT_UPDATED.value: ("document.update", "document", "standard"),
    EventType.DOCUMENT_DELETED.value: ("document.delete", "document", "standard"),
    EventType.DOCUMENT_CONVERTED.value: ("document.convert", "document", "standard"),
    EventType.DOCUMENT_BULK_DELETED.value: (
        "document.bulk_delete",
        "document",
        "standard",
    ),
    # Sync / import
    EventType.PRESTASHOP_SYNC_STARTED.value: (
        "sync.prestashop_start",
        "sync",
        "sensitive",
    ),
    EventType.PRESTASHOP_SYNC_COMPLETED.value: (
        "sync.prestashop_complete",
        "sync",
        "sensitive",
    ),
    EventType.PRESTASHOP_SYNC_FAILED.value: (
        "sync.prestashop_fail",
        "sync",
        "sensitive",
    ),
    EventType.PRODUCT_IMPORTED.value: ("import.product", "product", "sensitive"),
    EventType.ORDER_IMPORTED.value: ("import.order", "order", "sensitive"),
    EventType.CUSTOMER_IMPORTED.value: ("import.customer", "customer", "sensitive"),
    # Tax
    EventType.TAX_COUNTRY_DEFAULT_CHANGED.value: (
        "tax.country_default_change",
        "tax",
        "sensitive",
    ),
    # Auth / security
    EventType.AUTH_LOGIN_SUCCESS.value: ("auth.login", "auth", "security"),
    EventType.AUTH_LOGIN_FAILED.value: ("auth.login_failed", "auth", "security"),
    EventType.AUTH_LOGOUT.value: ("auth.logout", "auth", "security"),
    EventType.USER_ROLES_UPDATED.value: ("user.roles_update", "user", "security"),
    # Fiscal sensitive
    EventType.FISCAL_DOCUMENT_SENT_TO_SDI.value: (
        "fiscal.send_to_sdi",
        "fiscal_document",
        "sensitive",
    ),
    EventType.DOCUMENT_PDF_GENERATED.value: (
        "document.pdf_generate",
        "document",
        "sensitive",
    ),
    EventType.DOCUMENT_EXPORTED.value: (
        "document.export",
        "fiscal_document",
        "sensitive",
    ),
}

# Resource id candidates in event.data (first match wins)
RESOURCE_ID_KEYS = (
    "id_order",
    "order_id",
    "id_customer",
    "customer_id",
    "id_product",
    "product_id",
    "id_address",
    "address_id",
    "id_shipping",
    "shipping_id",
    "id_order_document",
    "id_fiscal_document",
    "id_document",
    "document_id",
    "id_user",
    "user_id",
    "id_tax",
    "id_audit_log",
    "id",
)


def get_mapping(event_type: str) -> Optional[AuditMapping]:
    return EVENT_AUDIT_MAP.get(event_type)


def subscribed_event_types() -> tuple[str, ...]:
    return tuple(EVENT_AUDIT_MAP.keys())


def extract_resource_id(data: dict) -> Optional[str]:
    if not data:
        return None
    for key in RESOURCE_ID_KEYS:
        if key in data and data[key] is not None:
            return str(data[key])
    return None


def extract_changes(data: dict) -> Optional[dict]:
    if not data:
        return None
    if "before" in data or "after" in data:
        return {
            "before": data.get("before"),
            "after": data.get("after"),
        }
    if "changes" in data and isinstance(data["changes"], dict):
        return data["changes"]
    return None
