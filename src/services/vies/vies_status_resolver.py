"""
Risoluzione snapshot `vies_status` per ordini importati da PrestaShop.

Decision tree (Fase 2 VIES):
- Paese fatturazione = IT → NULL
- Paese fatturazione ≠ IT:
  - Fattura non richiesta → NULL
  - Fattura richiesta, senza P.IVA → NULL
  - Fattura richiesta + P.IVA + VIES OK (PS) → eligible
  - Fattura richiesta + P.IVA + VIES KO (PS) → not_eligible
  - Fattura richiesta + P.IVA, esito VIES assente su PS → NULL
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.models.order import ViesStatus

# Campi custom PrestaShop (ordine) — primo match vince
_PRESTASHOP_VIES_FIELD_KEYS = (
    "vies_valid",
    "vat_number_valid",
    "valid_vat",
    "vies",
    "vies_checked",
    "vies_status",
)


def _normalize_iso(iso_code: Optional[str]) -> str:
    if not iso_code:
        return ""
    return str(iso_code).strip().upper()[:5]


def _coerce_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("1", "true", "yes", "si", "sì", "ok", "valid", "eligible"):
            return True
        if normalized in ("0", "false", "no", "invalid", "ko", "not_eligible", "not eligible"):
            return False
    return None


def has_invoice_vat_number(vat: Optional[str]) -> bool:
    """True se la P.IVA fatturazione è valorizzata (minimo 8 caratteri alfanumerici)."""
    if not vat:
        return False
    cleaned = "".join(c for c in str(vat).strip().upper() if c.isalnum())
    return len(cleaned) >= 8


def extract_prestashop_vies_valid(order: Dict[str, Any]) -> Optional[bool]:
    """
    Estrae l'esito verifica VIES dal payload ordine PrestaShop (campi custom modulo carrello).
    """
    for key in _PRESTASHOP_VIES_FIELD_KEYS:
        if key not in order:
            continue
        raw = order.get(key)
        if key == "vies_status" and isinstance(raw, str):
            normalized = raw.strip().lower()
            if normalized == ViesStatus.ELIGIBLE.value:
                return True
            if normalized == ViesStatus.NOT_ELIGIBLE.value:
                return False
            coerced = _coerce_bool(raw)
            if coerced is not None:
                return coerced
            continue
        coerced = _coerce_bool(raw)
        if coerced is not None:
            return coerced
    return None


def resolve_vies_status(
    billing_country_iso: Optional[str],
    is_invoice_requested: bool,
    invoice_vat: Optional[str],
    prestashop_vies_valid: Optional[bool],
) -> Optional[ViesStatus]:
    """
    Calcola lo snapshot `vies_status` da persistere sull'ordine.
    Non effettua chiamate VIES runtime: usa solo dati già presenti nel payload PS / indirizzo.
    """
    iso = _normalize_iso(billing_country_iso)
    if not iso or iso == "IT":
        return None

    if not is_invoice_requested:
        return None

    if not has_invoice_vat_number(invoice_vat):
        return None

    if prestashop_vies_valid is True:
        return ViesStatus.ELIGIBLE
    if prestashop_vies_valid is False:
        return ViesStatus.NOT_ELIGIBLE

    return None
