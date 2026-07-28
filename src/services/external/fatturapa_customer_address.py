"""Helper indirizzo cliente per FatturaPA (Italia + UE estero / VIES)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.external.province_service import province_service

# FAQ Agenzia delle Entrate: CAP generico per sedi con Nazione != IT
FOREIGN_CAP_PLACEHOLDER = "00000"
INDIRIZZO_MAX_LEN = 60
NUMERO_CIVICO_MAX_LEN = 8


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
    """Provincia fatturazione: sigla IT a 2 char; None per estero (non serializzare in XML)."""
    country = (country_iso or "IT").upper()
    if country != "IT":
        return None
    if not state or not str(state).strip():
        return ""
    raw = str(state).strip()
    abbr = province_service.get_province_abbreviation(raw)
    if abbr:
        return abbr.upper()
    if len(raw) == 2:
        return raw.upper()
    return raw[:2].upper() if len(raw) >= 2 else raw.upper()


def validate_customer_cap(postcode: Optional[str], country_iso: str) -> str:
    """
    CAP sede per XML FatturaPA.

    IT: esattamente 5 cifre.
    Estero: sempre ``00000`` (prassi FAQ AdE); il CAP reale va in Indirizzo via
    :func:`build_sede_fields`.
    """
    country = (country_iso or "IT").upper()
    if country != "IT":
        return FOREIGN_CAP_PLACEHOLDER
    cap = (postcode or "").strip()
    if not cap:
        raise ValueError("CAP cliente non può essere vuoto")
    digits = "".join(filter(str.isdigit, cap))
    if len(digits) != 5:
        raise ValueError(
            f"CAP italiano deve essere esattamente 5 cifre (ricevuto: '{cap}')"
        )
    return digits


def validate_customer_provincia(
    provincia: Optional[str], country_iso: str
) -> Optional[str]:
    """
    Provincia sede per XML FatturaPA.

    IT: obbligatoria, esattamente 2 caratteri.
    Estero: sempre None — lo schema ammette solo ``[A-Z]{2}`` (province italiane).
    """
    country = (country_iso or "IT").upper()
    if country != "IT":
        return None
    value = (provincia or "").strip()
    if not value:
        raise ValueError("Provincia obbligatoria per cliente con sede in Italia")
    prov = value.upper()
    if len(prov) != 2:
        raise ValueError(
            f"Provincia italiana deve essere esattamente 2 caratteri (ricevuto: '{value}')"
        )
    return prov


def build_sede_fields(
    *,
    indirizzo: str,
    nazione: str,
    comune: str,
    cap: Optional[str] = None,
    numero_civico: Optional[str] = None,
    provincia: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Campi blocco ``Sede`` FatturaPA v1.2 (ordine XSD).

    - ``NumeroCivico``: solo se non vuoto (pattern 1-8); altrimenti chiave assente
    - ``Provincia``: solo se ``Nazione == IT``; assente per estero
    - ``CAP``: IT 5 cifre; estero sempre ``00000`` (FAQ AdE), CAP reale in Indirizzo
    """
    country = (nazione or "IT").upper()
    indirizzo_clean = (indirizzo or "").replace(",", "").replace(";", "").strip()
    comune_clean = (comune or "").strip()
    raw_cap = (cap or "").strip()

    if country == "IT":
        cap_out = validate_customer_cap(raw_cap, "IT")
        provincia_out = validate_customer_provincia(provincia, "IT")
    else:
        # Prassi AdE: CAP XML = 00000; CAP reale eventualmente in Indirizzo
        cap_out = FOREIGN_CAP_PLACEHOLDER
        if raw_cap and raw_cap.upper() != FOREIGN_CAP_PLACEHOLDER:
            if raw_cap not in indirizzo_clean:
                combined = f"{indirizzo_clean} {raw_cap}".strip()
                indirizzo_clean = combined[:INDIRIZZO_MAX_LEN]
        provincia_out = None

    civico = (numero_civico or "").strip()
    if civico:
        civico = civico[:NUMERO_CIVICO_MAX_LEN]

    fields: Dict[str, Any] = {
        "Indirizzo": indirizzo_clean[:INDIRIZZO_MAX_LEN],
        "CAP": cap_out,
        "Comune": comune_clean[:INDIRIZZO_MAX_LEN],
        "Nazione": country,
    }
    if civico:
        fields["NumeroCivico"] = civico
    if provincia_out:
        fields["Provincia"] = provincia_out
    return fields
