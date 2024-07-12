from typing import Optional, Union

from pydantic import BaseModel, Field, validator
from datetime import datetime
from .customer_schema import CustomerResponseSchema, CustomerSchema, CustomerResponseWithoutAddressSchema


class AddressSchema(BaseModel):
    id_origin: Optional[int] = None
    id_country: Optional[int] = 0
    customer: CustomerSchema | int = 0
    company: Optional[str] = None
    firstname: str = Field(..., max_length=255)
    lastname: str = Field(..., max_length=255)
    address1: str = Field(..., max_length=128)
    address2: str = Field(..., max_length=128)
    state: str = Field(..., max_length=128)
    postcode: str = Field(..., max_length=12)
    city: str = Field(..., max_length=64)
    phone: str = Field(..., max_length=32)
    mobile_phone: str = Field(..., max_length=32)
    vat: str = Field(..., max_length=32)
    dni: str = Field(..., max_length=16)
    pec: str = Field(..., max_length=128)
    sdi: str = Field(..., max_length=128)


class CountryResponseSchema(BaseModel):
    id_country: int
    name: str
    iso_code: str


class AddressResponseSchema(BaseModel):
    id_address: int
    id_origin: int
    customer: CustomerResponseWithoutAddressSchema
    country: CountryResponseSchema
    company: str
    firstname: str
    lastname: str
    address1: str
    address2: str
    state: str
    postcode: str
    city: str
    phone: str
    mobile_phone: str
    vat: str
    dni: str
    pec: str
    sdi: str
    date_add: Union[datetime, str]

    @validator('date_add', pre=True, allow_reuse=True)
    def format_date(cls, value):
        if isinstance(value, datetime):
            return value.strftime('%d-%m-%Y')
        elif isinstance(value, str):
            try:
                # Prova a convertire la stringa in un datetime per assicurarti che sia nel formato corretto
                datetime.strptime(value, '%d-%m-%Y')
                return value  # Se è già una stringa corretta, restituiscila così com'è
            except ValueError:
                raise ValueError("date_add must be a valid 'DD-MM-YYYY' formatted string")
        raise ValueError("date_add must be a datetime object or a 'DD-MM-YYYY' formatted string")


class AllAddressResponseSchema(BaseModel):
    addresses: list[AddressResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
