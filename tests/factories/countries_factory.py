from typing import Any, Dict, Optional

from src.schemas.country_schema import CountrySchema

def create_country_data(
    id_origin: Optional[int] = 0,
    name: str = "Italia",
    iso_code: str = "IT"
) -> Dict[str, Any]:
    """Crea dati per un Country"""
    return {
        "id_origin": id_origin,
        "name": name,
        "iso_code": iso_code
    }

def create_country_schema(**kwargs) -> CountrySchema:
    """Crea un CountrySchema"""
    data = create_country_data(**kwargs)
    return CountrySchema(**data)