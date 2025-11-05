from typing import Optional

from pydantic import BaseModel, Field
from datetime import datetime


class CustomerSchema(BaseModel):
    """
        Schema di validazione per un cliente.

        Questo schema Pydantic è utilizzato per validare i dati di input relativi a un cliente
        all'interno di un'applicazione FastAPI. Assicura che tutti i dati necessari siano presenti
        e corretti prima di procedere con le operazioni di database o di logica di business.

        Attributes:
            id_origin (Optional[int]): Identificativo esterno opzionale del cliente. Può essere utilizzato
                                       per mantenere un collegamento con record cliente in sistemi esterni.
            id_lang (int): Identificativo della lingua preferita del cliente. Deve essere un numero positivo.
            firstname (str): Nome del cliente. Deve avere una lunghezza minima di 1 carattere e una massima di 100.
            lastname (str): Cognome del cliente. Come per il nome, deve avere una lunghezza minima di 1 carattere
                            e una massima di 100.
            email (EmailStr): Indirizzo email del cliente. Viene automaticamente validato per assicurarsi che rispetti
                              il formato standard degli indirizzi email.
    """
    id_origin: Optional[int] = 0
    id_lang: int = Field(..., gt=0)
    firstname: str = Field(..., min_length=1, max_length=100)
    lastname: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., max_length=150)


class CountryResponseSchema(BaseModel):
    id_country: int | None
    name: str | None
    iso_code: str | None


class AddressResponseSchema(BaseModel):
    id_address: int | None
    id_origin: int | None
    id_platform: int | None = Field(None, description="Platform ID (0 for manual addresses, 1 for PrestaShop)")
    country: Optional[CountryResponseSchema] = None
    company: str | None
    firstname: str | None
    lastname: str | None
    address1: str | None
    address2: str | None
    state: str | None
    postcode: str | None
    city: str | None
    phone: str | None
    mobile_phone: str | None
    vat: str | None
    dni: str | None
    pec: str | None
    sdi: str | None


class CustomerResponseSchema(BaseModel):
    id_customer: int | None
    id_origin: int | None
    id_lang: int | None
    firstname: str | None
    lastname: str | None
    email: str | None
    date_add: datetime | None
    addresses: Optional[list[AddressResponseSchema]] = None


class CustomerResponseWithoutAddressSchema(BaseModel):
    id_customer: int | None
    id_origin: int | None
    id_lang: int | None
    firstname: str | None
    lastname: str | None
    email: str | None
    date_add: datetime | None


class AllCustomerResponseSchema(BaseModel):
    customers: list[CustomerResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
