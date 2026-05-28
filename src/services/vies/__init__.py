"""VIES intra-UE B2B — risoluzione stato ordine al sync."""

from src.services.vies.vies_status_resolver import (
    extract_prestashop_vies_valid,
    has_invoice_vat_number,
    resolve_vies_status,
)

__all__ = [
    "extract_prestashop_vies_valid",
    "has_invoice_vat_number",
    "resolve_vies_status",
]
