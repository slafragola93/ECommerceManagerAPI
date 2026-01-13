"""
FedEx status mapping to internal shipping states

Maps FedEx derivedCode to internal shipping state codes.
The derivedCode is found in output.completeTrackResults[0].trackResults[0].derivedCode
"""
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
else:
    Session = None

# Default internal state id used when the FedEx status is unknown/not mapped
DEFAULT_STATE_ID: int = 12  # Stato Sconosciuto

# Mapping FedEx derivedCode to internal shipping state codes
FEDEX_DERIVED_CODE_MAPPING: Dict[str, int] = {
    # --- Pre-shipment ---
    "OC": 2,   # Order Created → Tracking Assegnato
    "AP": 2,   # At Pickup / Label Created → Tracking Assegnato

    # --- Pickup ---
    "PU": 3,   # Picked Up → Spedizione Presa In Carico

    # --- Transit ---
    "AR": 5,   # At FedEx Location → In Transito
    "DP": 5,   # Departed FedEx Location → In Transito
    "IT": 5,   # In Transit → In Transito
    "CC": 5,   # Clearance Complete → In Transito

    # --- Customs ---
    "CD": 9,   # Clearance Delay → In Dogana

    # --- Out for delivery ---
    "OD": 7,   # Out for Delivery → In Consegna

    # --- Delivered ---
    "DL": 8,   # Delivered → Consegnata

    # --- Exceptions / Delays ---
    "DO": 10,  # Delivery Exception → Bloccata
    "DE": 10,  # Delivery Exception
    "CA": 10,  # Customer not available → Bloccata
    "HL": 6,   # Held at Location → In Giacenza
    "LD": 6,   # Local Delay → In Giacenza
    "WE": 10,  # Weather Exception → Bloccata

    # --- Returns ---
    "RT": 11,  # Returned → Annullata
    "RS": 11,  # Return to Shipper → Annullata
}

# Legacy mapping for backward compatibility (if derivedCode is not available)
FEDEX_STATUS_MAPPING: Dict[str, int] = {
    # "Il tuo collo è in transito" → 5 (In Transito)
    "Il tuo collo è in transito": 5,
    "in transit": 5,
    "in_transit": 5,
    
    # "Il tuo collo è in consegna" → 7 (In Consegna)
    "Il tuo collo è in consegna": 7,
    "out for delivery": 7,
    "out_for_delivery": 7,
    
    # "Al momento non è disponibile nessuna data di consegna programmata" → 12 (Stato Sconosciuto)
    "Al momento non è disponibile nessuna data di consegna programmata": 12,
    "no scheduled delivery date available": 12,
    "no_delivery_date": 12,
    
    # "La consegna programmata è in sospeso" → 10 (Bloccato)
    "La consegna programmata è in sospeso": 10,
    "scheduled delivery is pending": 10,
    "delivery_pending": 10,
    
    # "Eccezione di consegna" (dogana) → 9 (In Dogana)
    "Eccezione di consegna - Ritardi doganali": 9,
    "delivery exception - customs": 9,
    "customs_delay": 9,
    "in customs": 9,
    
    # "Eccezione di consegna" (altri) → 10 (Bloccato)
    "Eccezione di consegna": 10,
    "delivery exception": 10,
    "exception": 10,
    
    # "Consegnato" → 8 (Consegnata)
    "Consegnato": 8,
    "delivered": 8,
    "delivery completed": 8,
    
    # "Picked up / Accepted" → 3 (Presa In Carico)
    "Picked up": 3,
    "Accepted": 3,
    "picked up": 3,
    "accepted": 3,
    "picked_up": 3,
    
    # "Label created / Manifest" → 2 (Tracking Assegnato)
    "Label created": 2,
    "Manifest": 2,
    "label created": 2,
    "manifest": 2,
    "label_created": 2,
    
    # "In preparation" → 1 (In Preparazione)
    "In preparation": 1,
    "in preparation": 1,
    "pre-shipment": 1,
    "pre_shipment": 1,
    
    # "At FedEx location / Held at location" → 6 (In Giacenza)
    "At FedEx location": 6,
    "Held at location": 6,
    "at fedex location": 6,
    "held at location": 6,
    "at_location": 6,
    "held_at_location": 6,
    
    # "Cancelled" → 11 (Annullato)
    "Cancelled": 11,
    "cancelled": 11,
    "canceled": 11,
    "cancellation": 11,
}


def map_fedex_derived_code_to_internal(derived_code: str) -> Optional[int]:
    """
    Map FedEx derivedCode to internal shipping state code
    
    Args:
        derived_code: FedEx derivedCode (e.g., "OC", "PU", "DL", etc.)
        
    Returns:
        Internal shipping state code or None if not found
    """
    if not derived_code:
        return None
    
    # Try exact match (case-insensitive)
    code_upper = derived_code.upper().strip()
    return FEDEX_DERIVED_CODE_MAPPING.get(code_upper)


def map_fedex_status_to_internal(fedex_status: str) -> Optional[int]:
    """
    Map FedEx status description to internal shipping state code (legacy method)
    
    Args:
        fedex_status: FedEx status description (case-insensitive)
        
    Returns:
        Internal shipping state code or None if not found
    """
    if not fedex_status:
        return None
    
    # Try exact match (case-insensitive)
    status_lower = fedex_status.lower().strip()
    for key, value in FEDEX_STATUS_MAPPING.items():
        if key.lower() == status_lower:
            return value
    
    # Try partial match
    for key, value in FEDEX_STATUS_MAPPING.items():
        if key.lower() in status_lower or status_lower in key.lower():
            return value
    
    return None


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

