from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field


class FedexConfigurationSchema(BaseModel):
    """FedEx Configuration schema for Ship API"""
    description: str = Field(..., max_length=255)
    
    # OAuth 2.0 Authentication fields
    client_id: str = Field(..., max_length=255)
    client_secret: str = Field(..., max_length=255)
    
    # Account information
    account_number: str = Field(..., max_length=50)
    
    # Shipper contact information
    person_name: str = Field(..., max_length=255)
    company_name: str = Field(..., max_length=255)
    phone_number: str = Field(..., max_length=50)
    contact_email: Optional[str] = Field(None, max_length=255)
    
    # Shipper address
    address: str = Field(..., max_length=255)
    city: str = Field(..., max_length=100)
    state_or_province_code: str = Field(..., max_length=10)
    postal_code: str = Field(..., max_length=20)
    country_code: str = Field(..., max_length=3)
    
    # Package defaults
    package_height: int = Field(..., gt=0)
    package_width: int = Field(..., gt=0)
    package_depth: int = Field(..., gt=0)
    default_weight: Decimal = Field(..., gt=0)
    
    # Shipment configuration
    service_type: str = Field(..., max_length=100)
    packaging_type: str = Field(..., max_length=100)
    pickup_type: str = Field(..., max_length=100)
    customs_charges: Optional[str] = Field(None, max_length=50)  # Used for paymentType (SENDER, RECIPIENT, THIRD_PARTY, ACCOUNT)


class FedexConfigurationResponseSchema(BaseModel):
    """FedEx Configuration response schema"""
    id_fedex_config: int
    id_carrier_api: int
    description: str
    client_id: str
    client_secret: str
    account_number: str
    person_name: str
    company_name: str
    phone_number: str
    contact_email: Optional[str]
    address: str
    city: str
    state_or_province_code: str
    postal_code: str
    country_code: str
    package_height: int
    package_width: int
    package_depth: int
    default_weight: Decimal
    service_type: str
    packaging_type: str
    pickup_type: str
    customs_charges: Optional[str]
    
    model_config = {"from_attributes": True}


class FedexConfigurationUpdateSchema(BaseModel):
    """FedEx Configuration update schema"""
    description: Optional[str] = Field(None, max_length=255)
    client_id: Optional[str] = Field(None, max_length=255)
    client_secret: Optional[str] = Field(None, max_length=255)
    account_number: Optional[str] = Field(None, max_length=50)
    person_name: Optional[str] = Field(None, max_length=255)
    company_name: Optional[str] = Field(None, max_length=255)
    phone_number: Optional[str] = Field(None, max_length=50)
    contact_email: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state_or_province_code: Optional[str] = Field(None, max_length=10)
    postal_code: Optional[str] = Field(None, max_length=20)
    country_code: Optional[str] = Field(None, max_length=3)
    package_height: Optional[int] = Field(None, gt=0)
    package_width: Optional[int] = Field(None, gt=0)
    package_depth: Optional[int] = Field(None, gt=0)
    default_weight: Optional[Decimal] = Field(None, gt=0)
    service_type: Optional[str] = Field(None, max_length=100)
    packaging_type: Optional[str] = Field(None, max_length=100)
    pickup_type: Optional[str] = Field(None, max_length=100)
    customs_charges: Optional[str] = Field(None, max_length=50)  # Used for paymentType
