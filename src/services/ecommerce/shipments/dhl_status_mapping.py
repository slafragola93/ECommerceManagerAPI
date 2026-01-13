"""
Mapping between DHL tracking event codes and internal shipping state IDs.

The mapping is used to derive an application-level shipping state from
carrier-specific (DHL) event codes during tracking normalization.
"""

from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
else:
    Session = None


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


def get_internal_state_name(state_code: int, db: Optional['Session'] = None) -> str:
    """
    Get internal state name from code.
    Recupera il nome dello stato dal database se disponibile, altrimenti usa un fallback.
    
    Args:
        state_code: Internal shipping state code
        db: Optional database session. Se fornito, recupera il nome dal DB.
        
    Returns:
        State name
    """
    # Se abbiamo una sessione DB, recupera dal database
    if db is not None:
        from src.services.ecommerce.shipments.shipping_state_utils import get_shipping_state_name
        db_name = get_shipping_state_name(db, state_code)
        if db_name:
            return db_name
    
    # Fallback hardcoded se DB non disponibile o stato non trovato
    state_names = {
        1: "In Preparazione",
        2: "Tracking Assegnato",
        3: "Presa In Carico",
        4: "Partita",
        5: "In Transito",
        6: "In Giacenza",
        7: "In Consegna",
        8: "Consegnata",
        9: "In Dogana",
        10: "Bloccato",
        11: "Annullato",
        12: "Stato Sconosciuto"
    }
    return state_names.get(state_code, "Stato Sconosciuto")

