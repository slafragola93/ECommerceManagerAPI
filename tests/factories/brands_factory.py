from typing import Any, Dict, Optional

from src.schemas.brand_schema import BrandSchema

def create_brand_data(
    id_origin: Optional[int] = None,
    id_platform: int = 1,
    id_store: Optional[int] = 1,
    name: str = "Brand Test"
) -> Dict[str, Any]:
    """Crea dati per un Brand"""
    return {
        "id_origin": id_origin,
        "id_store": id_store,
        "id_platform": id_platform,
        "name": name
    }

def create_brand_schema(**kwargs) -> BrandSchema:
    """Crea un BrandSchema"""
    data = create_brand_data(**kwargs)
    return BrandSchema(**data)