from typing import Any, Dict
from src.schemas.role_schema import RoleSchema

def create_role_data(
    name: str = "Role Test",
    permissions: str = "R"
) -> Dict[str, Any]:
    """Crea dati per un Role"""
    return {
        "name": name,
        "permissions": permissions
    }
    
def create_role_schema(**kwargs) -> RoleSchema:
    """Crea un RoleSchema"""
    data = create_role_data(**kwargs)
    return RoleSchema(**data)