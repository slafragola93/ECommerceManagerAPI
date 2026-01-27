from typing import Any, Dict, Optional
from src.schemas.tax_schema import TaxSchema

def create_tax_data(
    id_country: Optional[int] = None,
    is_default: int = 0,
    name: str = "Tax Test",
    **kwargs
) -> Dict[str, Any]:
    """Crea dati per un Tax"""
    return {
        "id_country": id_country,
        "is_default": is_default,
        "name": name,
        **kwargs
    }
    
def create_tax_schema(**kwargs) -> TaxSchema:
    """Crea un TaxSchema"""
    data = create_tax_data(**kwargs)
    return TaxSchema(**data)