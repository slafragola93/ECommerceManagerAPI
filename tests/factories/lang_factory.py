from typing import Any, Dict, Optional

from src.schemas.lang_schema import LangSchema


def create_lang_data(
    id_origin: Optional[int] = 0,
    name: str = "Italiam",
    iso_code: str = "it"
) -> Dict[str, Any]:
    """Crea dati per un Lang"""
    return {
        "id_origin": id_origin,
        "name": name,
        "iso_code": iso_code
    }

def create_lang_schema(**kwargs) -> LangSchema:
    """Crea un LangSchema"""
    data = create_lang_data(**kwargs)
    return LangSchema(**data)