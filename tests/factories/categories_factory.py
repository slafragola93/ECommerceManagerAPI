from typing import Any, Dict, Optional

from src.schemas.category_schema import CategorySchema

def create_category_data(
    id_origin: Optional[int] = None,
    id_store: Optional[int] = 1,
    name: str = "Category Test"
) -> Dict[str, Any]:
    """Crea dati per una Categoria"""
    return {
        "id_origin": id_origin,
        "id_store": id_store,
        "name": name
    }

def create_category_schema(**kwargs) -> CategorySchema:
    """Crea un CategorySchema"""
    data = create_category_data(**kwargs)
    return CategorySchema(**data)