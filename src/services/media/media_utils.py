"""
Utility per gestione file media, directory e path
"""
import os
from typing import Optional
from pathlib import Path


def ensure_store_logo_directory(id_store: int) -> str:
    """
    Crea la directory per il logo dello store se non esiste.
    
    Args:
        id_store: ID dello store
    
    Returns:
        str: Path completo del file logo (media/logos/stores/{id_store}/logo.png)
    """
    logo_dir = Path(f"media/logos/stores/{id_store}")
    logo_path = logo_dir / "logo.png"
    
    # Crea directory se non esiste
    logo_dir.mkdir(parents=True, exist_ok=True)
    
    return str(logo_path)


def get_store_logo_path(store, fallback_path: Optional[str] = None) -> Optional[str]:
    """
    Recupera il path del logo dello store se configurato e il file esiste.
    Altrimenti restituisce il fallback.
    
    Args:
        store: Istanza Store con metodo get_logo_path()
        fallback_path: Path di fallback se logo store non disponibile
    
    Returns:
        Optional[str]: Path del logo store se disponibile, altrimenti fallback_path o None
    """
    if not store:
        return fallback_path
    
    # Recupera path logo dallo store
    logo_path = store.get_logo_path()
    
    if not logo_path:
        return fallback_path
    
    # Verifica esistenza file
    if os.path.exists(logo_path):
        return logo_path
    
    # Se file non esiste, usa fallback
    return fallback_path
