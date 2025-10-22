from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field, EmailStr


class DhlConfigurationSchema(BaseModel):
    description: str = Field(..., max_length=255)
    account_number: int = Field(..., gt=0)
    password: str = Field(..., max_length=255)
    site_id: str = Field(..., max_length=100)
    company_name: str = Field(..., max_length=255)
    city: str = Field(..., max_length=100)
    address: str = Field(..., max_length=255)
    postal_code: str = Field(..., max_length=20)
    country_iso: str = Field(..., max_length=3, pattern=r'^[A-Z]{2,3}$')
    country: str = Field(..., max_length=100)
    reference_person: str = Field(..., max_length=255)
    email: EmailStr = Field(...)
    phone: str = Field(..., max_length=50, pattern=r'^\+?[0-9]{10,15}$')
    default_weight: Decimal = Field(..., gt=0)
    package_height: int = Field(..., gt=0)
    package_width: int = Field(..., gt=0)
    package_depth: int = Field(..., gt=0)
    goods_description: Optional[str] = None
    
    # Select values (salvano solo il valore scelto come stringa)
    layout: str = Field(..., max_length=20)
    cash_on_delivery: str = Field(..., max_length=10)
    print_waybill: str = Field(..., max_length=10)
    sku_quantity: str = Field(..., max_length=10)
    national_service: str = Field(..., max_length=100)
    international_service: str = Field(..., max_length=100)


class DhlConfigurationResponseSchema(BaseModel):
    id_dhl_config: int
    id_carrier_api: int
    description: str
    account_number: int
    password: str
    site_id: str
    company_name: str
    city: str
    address: str
    postal_code: str
    country_iso: str
    country: str
    reference_person: str
    email: str
    phone: str
    default_weight: Decimal
    package_height: int
    package_width: int
    package_depth: int
    goods_description: Optional[str]
    layout: str
    cash_on_delivery: str
    print_waybill: str
    sku_quantity: str
    national_service: str
    international_service: str
    
    model_config = {"from_attributes": True}


class DhlConfigurationUpdateSchema(BaseModel):
    description: Optional[str] = Field(None, max_length=255)
    account_number: Optional[int] = Field(None, gt=0)
    password: Optional[str] = Field(None, max_length=255)
    site_id: Optional[str] = Field(None, max_length=100)
    company_name: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    postal_code: Optional[str] = Field(None, max_length=20)
    country_iso: Optional[str] = Field(None, max_length=3, pattern=r'^[A-Z]{2,3}$')
    country: Optional[str] = Field(None, max_length=100)
    reference_person: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50, pattern=r'^\+?[0-9]{10,15}$')
    default_weight: Optional[Decimal] = Field(None, gt=0)
    package_height: Optional[int] = Field(None, gt=0)
    package_width: Optional[int] = Field(None, gt=0)
    package_depth: Optional[int] = Field(None, gt=0)
    goods_description: Optional[str] = None
    layout: Optional[str] = Field(None, max_length=20)
    cash_on_delivery: Optional[str] = Field(None, max_length=10)
    print_waybill: Optional[str] = Field(None, max_length=10)
    sku_quantity: Optional[str] = Field(None, max_length=10)
    national_service: Optional[str] = Field(None, max_length=100)
    international_service: Optional[str] = Field(None, max_length=100)
