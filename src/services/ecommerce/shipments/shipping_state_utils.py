"""
Utility functions for retrieving shipping states from the database.

This module provides shared functions for all carrier services (BRT, DHL, FedEx)
to retrieve shipping state information from the database using hydrated queries.
"""
from typing import Dict, Optional
from sqlalchemy.orm import Session
from src.models.shipping_state import ShippingState


def get_shipping_states_dict(db: Session) -> Dict[int, str]:
    """
    Recupera tutti gli stati di spedizione dal database e li restituisce come dizionario.
    Usa una query idratata per ottimizzare le performance.
    
    Args:
        db: Database session
        
    Returns:
        Dict con mapping {id_shipping_state: name}
        Esempio: {1: "In Preparazione", 2: "Tracking Assegnato", ...}
    """
    try:
        # Query idratata: carica tutti gli stati in memoria
        states = db.query(ShippingState).all()
        
        # Crea dizionario {id: name}
        states_dict = {state.id_shipping_state: state.name for state in states}
        
        return states_dict
    except Exception as e:
        # In caso di errore, restituisci dizionario vuoto
        # I servizi possono gestire il fallback
        return {}


def get_shipping_state_name(db: Session, state_id: int) -> Optional[str]:
    """
    Recupera il nome di uno stato di spedizione dato il suo ID.
    
    Args:
        db: Database session
        state_id: ID dello stato di spedizione
        
    Returns:
        Nome dello stato o None se non trovato
    """
    try:
        state = db.query(ShippingState).filter(
            ShippingState.id_shipping_state == state_id
        ).first()
        
        return state.name if state else None
    except Exception as e:
        return None


def get_default_shipping_state_id(db: Session) -> int:
    """
    Recupera l'ID dello stato di default (Stato Sconosciuto).
    Se non trovato, restituisce 12 come fallback.
    
    Args:
        db: Database session
        
    Returns:
        ID dello stato di default (tipicamente 12 per "Stato Sconosciuto")
    """

    # Cerca lo stato "Stato Sconosciuto" o simile
    state = db.query(ShippingState).filter(
        ShippingState.name.ilike("%sconosciuto%")
    ).first()
    
    if state:
        return state.id_shipping_state
    
    # Fallback: cerca per ID 12
    state = db.query(ShippingState).filter(
        ShippingState.id_shipping_state == 12
    ).first()
    
    if state:
        return state.id_shipping_state



def get_shipping_states_cache(db: Session) -> Dict[int, str]:
    """
    Versione cached di get_shipping_states_dict.
    Per ora restituisce semplicemente get_shipping_states_dict,
    ma può essere estesa per implementare caching in memoria.
    
    Args:
        db: Database session
        
    Returns:
        Dict con mapping {id_shipping_state: name}
    """
    return get_shipping_states_dict(db)
