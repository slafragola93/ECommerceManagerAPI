from typing import Optional
from pydantic import BaseModel, Field


class FedexConfigurationSchema(BaseModel):
    description: str = Field(..., max_length=255)
    client_id: str = Field(..., max_length=255)
    client_secret: str = Field(..., max_length=255)
    account_number: int = Field(..., gt=0)
    person_name: str = Field(..., max_length=255)
    company_name: str = Field(..., max_length=255)
    phone_number: str = Field(..., max_length=50, pattern=r'^\+?[0-9]{10,15}$')
    address: str = Field(..., max_length=255)
    city: str = Field(..., max_length=100)
    state_or_province_code: str = Field(..., max_length=10, pattern=r'^[A-Z]{2,3}$')
    postal_code: str = Field(..., max_length=20)
    country_code: str = Field(..., max_length=3, pattern=r'^[A-Z]{2,3}$')
    package_height: int = Field(..., gt=0)
    package_width: int = Field(..., gt=0)
    package_depth: int = Field(..., gt=0)
    default_weight: int = Field(..., gt=0)
    
    # Select values (salvano solo il valore scelto come stringa)
    sandbox: str = Field(..., max_length=10)
    service_type: str = Field(..., max_length=100)
    packaging_type: str = Field(..., max_length=100)
    pickup_type: str = Field(..., max_length=100)
    customs_charges: str = Field(..., max_length=50)
    format: str = Field(..., max_length=20)
    notes_field: str = Field(..., max_length=10)


class FedexConfigurationResponseSchema(BaseModel):
    id_fedex_config: int
    id_carrier_api: int
    description: str
    client_id: str
    client_secret: str
    account_number: int
    person_name: str
    company_name: str
    phone_number: str
    address: str
    city: str
    state_or_province_code: str
    postal_code: str
    country_code: str
    package_height: int
    package_width: int
    package_depth: int
    default_weight: int
    sandbox: str
    service_type: str
    packaging_type: str
    pickup_type: str
    customs_charges: str
    format: str
    notes_field: str
    
    model_config = {"from_attributes": True}


class FedexConfigurationUpdateSchema(BaseModel):
    description: Optional[str] = Field(None, max_length=255)
    client_id: Optional[str] = Field(None, max_length=255)
    client_secret: Optional[str] = Field(None, max_length=255)
    account_number: Optional[int] = Field(None, gt=0)
    person_name: Optional[str] = Field(None, max_length=255)
    company_name: Optional[str] = Field(None, max_length=255)
    phone_number: Optional[str] = Field(None, max_length=50, pattern=r'^\+?[0-9]{10,15}$')
    address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state_or_province_code: Optional[str] = Field(None, max_length=10, pattern=r'^[A-Z]{2,3}$')
    postal_code: Optional[str] = Field(None, max_length=20)
    country_code: Optional[str] = Field(None, max_length=3, pattern=r'^[A-Z]{2,3}$')
    package_height: Optional[int] = Field(None, gt=0)
    package_width: Optional[int] = Field(None, gt=0)
    package_depth: Optional[int] = Field(None, gt=0)
    default_weight: Optional[int] = Field(None, gt=0)
    sandbox: Optional[str] = Field(None, max_length=10)
    service_type: Optional[str] = Field(None, max_length=100)
    packaging_type: Optional[str] = Field(None, max_length=100)
    pickup_type: Optional[str] = Field(None, max_length=100)
    customs_charges: Optional[str] = Field(None, max_length=50)
    format: Optional[str] = Field(None, max_length=20)
    notes_field: Optional[str] = Field(None, max_length=10)
