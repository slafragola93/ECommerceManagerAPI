from typing import Any, Dict, Optional

from src.schemas.carrier_schema import CarrierSchema

def create_carrier_data(
    id_origin: Optional[int] = None,
    id_store: Optional[int] = 1,
    name: str = "Carrier Test"
) -> Dict[str, Any]:
    """Crea dati per un Carrier"""
    return {
        "id_origin": id_origin,
        "id_store": id_store,
        "name": name
    }

def create_carrier_schema(**kwargs) -> CarrierSchema:
    """Crea un CarrierSchema"""
    data = create_carrier_data(**kwargs)
    return CarrierSchema(**data)