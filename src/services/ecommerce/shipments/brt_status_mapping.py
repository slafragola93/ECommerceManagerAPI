"""
Mapping between BRT tracking event descriptions and internal shipping state IDs.

BRT tracking events don't have standardized codes like DHL, so we map based on
event descriptions (descrizione field) using keyword matching.
"""

from typing import Dict

# Default internal state id used when the BRT event is unknown/not mapped
DEFAULT_STATE_ID: int = 12  # Stato Sconosciuto

# Keywords in BRT event descriptions -> internal shipping_state.id_shipping_state
# These are matched case-insensitively against the event description
BRT_DESCRIPTION_KEYWORDS: Dict[str, int] = {
    # Presa In Carico / Accettazione
    "presa in carico": 2,
    "accettato": 2,
    "accettazione": 2,
    "ricevuto": 2,
    "in lavorazione": 2,
    
    # Partita
    "partita": 4,
    "partenza": 4,
    "in partenza": 4,
    
    # In Transito
    "in transito": 5,
    "transito": 5,
    "in viaggio": 5,
    "in consegna al corriere": 5,
    
    # In Giacenza/Reso
    "in giacenza": 6,
    "giacenza": 6,
    "reso": 6,
    "ritorno": 6,
    
    # In Consegna
    "in consegna": 7,
    "consegna": 7,
    "fuori per la consegna": 7,
    "in consegna al destinatario": 7,
    
    # Consegnata
    "consegnato": 8,
    "consegnata": 8,
    "consegna effettuata": 8,
    "consegna completata": 8,
    
    # In Dogana
    "dogana": 9,
    "in dogana": 9,
    "sdoganamento": 9,
    "sdoganato": 9,
    
    # Bloccato
    "bloccato": 10,
    "ritardato": 10,
    "problema": 10,
    "anomalia": 10,
    
    # Annullato
    "annullato": 11,
    "cancellato": 11,
    "annullata": 11,
}


def map_brt_description_to_internal_state_id(description: str | None) -> int:
    """
    Return internal state id for a BRT event description using keyword matching.
    
    - Normalizes the description to lowercase
    - Matches against keyword dictionary
    - Falls back to DEFAULT_STATE_ID if no match found
    
    Args:
        description: BRT event description (descrizione field)
        
    Returns:
        Internal shipping_state.id_shipping_state
    """
    if not description:
        return DEFAULT_STATE_ID
    
    desc_lower = description.lower().strip()
    
    # Try exact keyword match first
    if desc_lower in BRT_DESCRIPTION_KEYWORDS:
        return BRT_DESCRIPTION_KEYWORDS[desc_lower]
    
    # Try substring matching (check if any keyword is contained in description)
    for keyword, state_id in BRT_DESCRIPTION_KEYWORDS.items():
        if keyword in desc_lower:
            return state_id
    
    # No match found
    return DEFAULT_STATE_ID


def map_brt_code_to_internal_state_id(brt_code: str | None) -> int:
    """
    Alias for map_brt_description_to_internal_state_id for consistency with DHL.
    
    BRT doesn't use codes, but this function allows the same interface as DHL.
    """
    return map_brt_description_to_internal_state_id(brt_code)

