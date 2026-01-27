from typing import Any, Dict
from src.schemas.sectional_schema import SectionalSchema

def create_sectional_data(
    name: str = "Sectional Test"
) -> Dict[str, Any]:
    """Crea dati per un Sectional"""
    return {
        "name": name
    }
    
def create_sectional_schema(**kwargs) -> SectionalSchema:
    """Crea un SectionalSchema"""
    data = create_sectional_data(**kwargs)
    return SectionalSchema(**data)