"""
Factory per creare dati Address
"""

from ast import Dict
import datetime
from typing import Any, Optional

from src.schemas.address_schema import AddressSchema

def create_address_data(
    id_origin: Optional[int] = None,
    id_store: Optional[int] = 1,
    id_country: Optional[int] = 1,
    id_customer: Optional[int] = 1,
    company: str = "Company Test",
    firstname: str = "John",
    lastname: str = "Doe",
    address1: str = "Via dei condotti 8",
    address2: str = None,
    city: str = "Roma",
    postcode: str = "00187",
    state: str = "RM",
    phone: str = "1234567890",
    date_add: datetime = datetime.now(),
    **kwargs
) -> Dict[str, Any]:
    """Crea dati per un Address"""

    return {
        "id_origin": id_origin,
        "id_store": id_store,
        "id_country": id_country,
        "id_customer": id_customer,
        "company": company,
        "firstname": firstname,
        "lastname": lastname,
        "address1": address1,
        "address2": address2,
        "city": city,
        "postcode": postcode,
        "state": state,
        "phone": phone,
        "date_add": date_add,
        **kwargs
    }


def create_address_schema(**kwargs) -> AddressSchema:
    """Crea un AddressSchema"""
    data = create_address_data(**kwargs)
    return AddressSchema(**data)

