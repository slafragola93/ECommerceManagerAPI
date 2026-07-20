"""Helper indirizzo cliente per FatturaPA (Italia + UE estero / VIES)."""

from __future__ import annotations

from typing import Optional

from src.services.external.province_service import province_service


def normalize_customer_vat(vat_raw: Optional[str], country_iso: str) -> str:
    """Normalizza P.IVA cliente: solo cifre per IT, alfanumerico per estero."""
    if not vat_raw:
        return ""
    country = (country_iso or "IT").upper()
    cleaned = "".join(filter(str.isalnum, vat_raw.upper()))
    if country == "IT":
        return "".join(filter(str.isdigit, cleaned))
    if cleaned.startswith(country):
        cleaned = cleaned[len(country) :]
    return cleaned


def resolve_codice_destinatario(
    country_iso: str, customer_sdi: Optional[str] = None
) -> str:
    """Codice destinatario SDI: XXXXXXX per clienti esteri, altrimenti SDI o 0000000."""
    country = (country_iso or "IT").upper()
    if country != "IT":
        return "XXXXXXX"
    sdi = (customer_sdi or "").strip()
    if len(sdi) == 7:
        return sdi
    return "0000000"


def resolve_invoice_state(
    state: Optional[str], country_iso: str
) -> Optional[str]:
    """Provincia/regione fatturazione: sigla IT a 2 char, testo libero per estero."""
    country = (country_iso or "IT").upper()
    if not state or not str(state).strip():
        return None if country != "IT" else ""
    raw = str(state).strip()
    if country == "IT":
        abbr = province_service.get_province_abbreviation(raw)
        if abbr:
            return abbr.upper()
        if len(raw) == 2:
            return raw.upper()
        return raw[:2].upper() if len(raw) >= 2 else raw.upper()
    return raw[:10]


def validate_customer_cap(postcode: Optional[str], country_iso: str) -> str:
    """Valida CAP sede cliente (5 cifre IT, 3-10 caratteri estero)."""
    country = (country_iso or "IT").upper()
    cap = (postcode or "").strip()
    if not cap:
        raise ValueError("CAP cliente non può essere vuoto")
    if country == "IT":
        digits = "".join(filter(str.isdigit, cap))
        if len(digits) != 5:
            raise ValueError(
                f"CAP italiano deve essere esattamente 5 cifre (ricevuto: '{cap}')"
            )
        return digits
    if len(cap) < 3 or len(cap) > 10:
        raise ValueError(
            f"CAP estero deve essere tra 3 e 10 caratteri (ricevuto: '{cap}')"
        )
    return cap


def validate_customer_provincia(
    provincia: Optional[str], country_iso: str
) -> Optional[str]:
    """Valida provincia sede cliente (obbligatoria 2 char per IT, opzionale estero)."""
    country = (country_iso or "IT").upper()
    value = (provincia or "").strip()
    if not value:
        if country == "IT":
            raise ValueError("Provincia obbligatoria per cliente con sede in Italia")
        return None
    if country == "IT":
        prov = value.upper()
        if len(prov) != 2:
            raise ValueError(
                f"Provincia italiana deve essere esattamente 2 caratteri (ricevuto: '{value}')"
            )
        return prov
    if len(value) < 2 or len(value) > 10:
        raise ValueError(
            f"Provincia estera deve essere tra 2 e 10 caratteri (ricevuto: '{value}')"
        )
    return value[:10]
