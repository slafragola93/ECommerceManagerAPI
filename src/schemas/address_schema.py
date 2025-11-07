from typing import Optional, Union

from pydantic import BaseModel, Field, validator
from datetime import datetime, date
from .customer_schema import CustomerResponseSchema, CustomerSchema, CustomerResponseWithoutAddressSchema


class AddressSchema(BaseModel):
    id_origin: Optional[int] = None
    id_platform: Optional[int] = Field(None, ge=0)
    id_country: Optional[int] = None
    id_customer: Optional[int] = None
    company: Optional[str] = None
    firstname: str = Field(..., max_length=255)
    lastname: str = Field(..., max_length=255)
    address1: str = Field(..., max_length=128)
    address2: Optional[str] = Field(None, max_length=128)
    state: str = Field(..., max_length=128)
    postcode: str = Field(..., max_length=12)
    city: str = Field(..., max_length=64)
    phone: str = Field(..., max_length=32)
    mobile_phone: Optional[str] = Field(None, max_length=32)
    vat: Optional[str] = Field(None, max_length=32)
    dni: Optional[str] = Field(None, max_length=16)
    pec: Optional[str] = Field(None, max_length=128)
    sdi: Optional[str] = Field(None, max_length=128)
    ipa: Optional[str] = Field(None, max_length=128)


class CountryResponseSchema(BaseModel):
    id_country: int | None
    name: str | None
    iso_code: str | None


class AddressResponseSchema(BaseModel):
    id_address: int | None
    id_origin: int | None
    id_platform: int | None = None
    customer: Optional[CustomerResponseWithoutAddressSchema] = None
    country: CountryResponseSchema | None
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
    ipa: Optional[str] = None
    date_add: Union[datetime, str] | None

    @validator('date_add', pre=True, allow_reuse=True)
    def format_date(cls, value):
        if isinstance(value, datetime):
            return value.strftime('%d-%m-%Y')
        elif isinstance(value, date):
            return value.strftime('%d-%m-%Y')
        elif isinstance(value, str):
            try:
                # Prova a convertire la stringa in un datetime per assicurarti che sia nel formato corretto
                datetime.strptime(value, '%d-%m-%Y')
                return value  # Se è già una stringa corretta, restituiscila così com'è
            except ValueError:
                raise ValueError("date_add must be a valid 'DD-MM-YYYY' formatted string")
        elif value is None:
            return None
        raise ValueError("date_add must be a datetime/date object or a 'DD-MM-YYYY' formatted string")
    
    class Config:
        from_attributes = True


class AllAddressResponseSchema(BaseModel):
    addresses: list[AddressResponseSchema]
    total: int
    page: int
    limit: int


class AddressesByCustomerResponseSchema(BaseModel):
    addresses: list[AddressResponseSchema]
    total: int