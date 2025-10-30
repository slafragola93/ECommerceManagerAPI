"""
Mapping between DHL tracking event codes and internal shipping state IDs.

The mapping is used to derive an application-level shipping state from
carrier-specific (DHL) event codes during tracking normalization.
"""

from typing import Dict


# Default internal state id used when the DHL code is unknown/not mapped
DEFAULT_STATE_ID: int = 12  # Stato Sconosciuto


# DHL code -> internal shipping_state.id_shipping_state
DHL_TO_INTERNAL_STATE_ID: Dict[str, int] = {
    "PU": 2,   # Presa In Carico
    "AF": 5,   # In Transito
    "PL": 5,   # In Transito
    "DF": 4,   # Partita
    "RR": 9,   # In Dogana (aggiornamento stato dogana)
    "CR": 5,   # In Transito (dogana completata → torni in transito)
    "AR": 5,   # In Transito (arrivata al delivery facility)
    "WC": 7,   # In Consegna
    "OK": 8,   # Consegnata
    # Codici utili non presenti nell'esempio JSON
    "OH": 10,  # Bloccato
    "CD": 10,  # Bloccato (clearance delay)
    "CA": 11,  # Annullato
    "RT": 6,   # In Giacenza/Reso
}


def map_dhl_code_to_internal_state_id(dhl_code: str | None) -> int:
    """Return internal state id for a DHL event code with safe fallback.

    - Normalizes the code to uppercase and trims whitespace
    - Falls back to DEFAULT_STATE_ID if missing/unknown
    """
    if not dhl_code:
        return DEFAULT_STATE_ID
    code = dhl_code.strip().upper()
    return DHL_TO_INTERNAL_STATE_ID.get(code, DEFAULT_STATE_ID)


