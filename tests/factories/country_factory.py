
from ast import Dict
from typing import Any

from src.schemas.country_schema import CountrySchema


def create_country_data(
    id_country: int = 1,
    name: str = "Italia",
    iso_code: str = "IT",
    id_origin: int = 1,
) -> Dict[str, Any]:
    """Crea dati per un country"""
    
    return {
        "id_country": id_country,
        "name": name,
        "iso_code": iso_code,
        "id_origin": id_origin,
    }


def create_country_schema(**kwargs) -> CountrySchema:
    """Crea un CountrySchema"""
    data = create_country_data(**kwargs)
    return CountrySchema(**data)