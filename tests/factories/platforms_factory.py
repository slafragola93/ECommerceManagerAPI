from typing import Dict
from typing_extensions import Any

from src.schemas.platform_schema import PlatformSchema

def create_platform_data(
    name: str = "Platform Test",
    is_default: bool = True) -> Dict[str, Any]:
    """Crea dati per una Platform"""
    return {
        "name": name,
        "is_default": is_default
    }

def create_platform_schema(**kwargs) -> PlatformSchema:
    """Crea un PlatformSchema"""
    data = create_platform_data(**kwargs)
    return PlatformSchema(**data)