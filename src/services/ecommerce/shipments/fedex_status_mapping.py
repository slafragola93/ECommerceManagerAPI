"""
FedEx status mapping to internal shipping states

This mapping will be used when implementing tracking functionality (Phase 2).
For now, it's prepared for future use.
"""
from typing import Dict, Optional

# Default internal state id used when the FedEx status is unknown/not mapped
DEFAULT_STATE_ID: int = 12  # Stato Sconosciuto

# Mapping FedEx status descriptions to internal shipping state codes
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


def map_fedex_status_to_internal(fedex_status: str) -> Optional[int]:
    """
    Map FedEx status description to internal shipping state code
    
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


def get_internal_state_name(state_code: int) -> str:
    """
    Get internal state name from code
    
    Args:
        state_code: Internal shipping state code
        
    Returns:
        State name
    """
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

