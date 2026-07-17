"""Risoluzione ISO paese → locale PDF."""
from __future__ import annotations

from typing import Optional

# ISO paese → codice locale PDF (lowercase)
_ISO_TO_LOCALE = {
    "IT": "it",
    "FR": "fr",
    "DE": "de",
    "AT": "de",
    "ES": "es",
    "GB": "en",
    "UK": "en",
    "IE": "en",
    "US": "en",
}

_DEFAULT_LOCALE = "en"
_DEFAULT_IT_LOCALE = "it"


def resolve_country_iso(invoice_address=None, delivery_address=None) -> Optional[str]:
    """Estrae ISO paese da indirizzo fattura (preferito) o consegna."""
    for addr in (invoice_address, delivery_address):
        if not addr:
            continue
        country = getattr(addr, "country", None)
        if country and getattr(country, "iso_code", None):
            return str(country.iso_code).upper()
    return None


def resolve_invoice_locale(country_iso: Optional[str]) -> str:
    """
    Mappa ISO paese → locale etichette fattura.

    IT → it, FR → fr, DE/AT → de, ES → es.
    Paese sconosciuto / assente → en (estero generico).
    """
    if not country_iso:
        return _DEFAULT_IT_LOCALE
    iso = str(country_iso).upper().strip()
    if iso == "IT":
        return "it"
    return _ISO_TO_LOCALE.get(iso, _DEFAULT_LOCALE)
