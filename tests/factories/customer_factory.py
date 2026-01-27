from typing import Any, Dict, Optional

from src.schemas.customer_schema import CustomerSchema


def create_customer_data(
    id_origin: Optional[int] = None,
    id_lang: int = 1,
    id_store: Optional[int] = 1,
    firstname: str = "John",
    lastname: str = "Doe",
    email: str = "john.doe@example.com"
) -> Dict[str, Any]:
    """Crea dati per un Customer"""
    return {
        "id_origin": id_origin,
        "id_lang": id_lang,
        "id_store": id_store,
        "firstname": firstname,
        "lastname": lastname,
        "email": email
    }

def create_customer_schema(**kwargs) -> CustomerSchema:
    """Crea un CustomerSchema"""
    data = create_customer_data(**kwargs)
    return CustomerSchema(**data)