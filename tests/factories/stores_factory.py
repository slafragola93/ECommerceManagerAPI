from typing import Any, Dict, Optional
from src.schemas.store_schema import StoreSchema

def create_store_data(
    id_platform: int = 1,
    name: str = "Store Test",
    base_url: str = "https://store.test",
    api_key: str = "1234567890",
    logo: Optional[str] = None,
    is_active: bool = True,
    is_default: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """Crea dati per un Store"""
    return {
        "id_platform": id_platform,
        "name": name,  
        "base_url": base_url,
        "api_key": api_key,
        "logo": logo,
        "is_active": is_active,
        "is_default": is_default,
        **kwargs
    }
    
def create_store_schema(**kwargs) -> StoreSchema:
    """Crea un StoreSchema"""
    data = create_store_data(**kwargs)
    return StoreSchema(**data)