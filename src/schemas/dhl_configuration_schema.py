from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field, EmailStr
from enum import Enum


class UnitOfMeasureEnum(str, Enum):
    METRIC = "Metric"
    IMPERIAL = "Imperial"


class LabelFormatEnum(str, Enum):
    PDF = "PDF"
    ZPL = "ZPL"


class DhlConfigurationSchema(BaseModel):
    """DHL Configuration schema for MyDHL API"""
    description: str = Field(..., max_length=255)
    shipper_account_number: str = Field(..., max_length=255)  # renamed from account_number
    company_name: str = Field(..., max_length=255)
    city: str = Field(..., max_length=100)
    address: str = Field(..., max_length=255)
    postal_code: str = Field(..., max_length=20)
    country_code: str = Field(..., max_length=2, pattern=r'^[A-Z]{2}$')  # renamed from country_iso, 2-letter ISO
    reference_person: str = Field(..., max_length=255)
    email: EmailStr = Field(...)
    phone: str = Field(..., max_length=50, pattern=r'^\+?[0-9]{10,15}$')
    default_weight: Decimal = Field(..., gt=0)
    package_height: int = Field(..., gt=0)
    package_width: int = Field(..., gt=0)
    package_depth: int = Field(..., gt=0)
    goods_description: Optional[str] = None
    
    # MyDHL API specific fields
    label_format: LabelFormatEnum = Field(default=LabelFormatEnum.PDF)  # renamed from layout
    unit_of_measure: UnitOfMeasureEnum = Field(default=UnitOfMeasureEnum.METRIC)
    default_is_customs_declarable: bool = Field(default=False)
    default_incoterm: Optional[str] = Field(None, max_length=3)
    duties_account_number: Optional[str] = Field(None, max_length=255)
    payer_account_number: Optional[str] = Field(None, max_length=255)
    province_code: Optional[str] = Field(None, max_length=50)
    tax_id: Optional[str] = Field(None, max_length=255)  # VAT/EORI
    pickup_is_requested: bool = Field(default=False)
    pickup_close_time: Optional[str] = Field(None, max_length=5, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')  # HH:mm format
    pickup_location: Optional[str] = Field(None, max_length=255)
    
    # Service codes
    default_product_code_domestic: str = Field(..., max_length=100)  # renamed from national_service
    default_product_code_international: str = Field(..., max_length=100)  # renamed from international_service
    
    # COD fields (replaced cash_on_delivery)
    cod_enabled: bool = Field(default=False)
    cod_currency: Optional[str] = Field(None, max_length=3)


class DhlConfigurationResponseSchema(BaseModel):
    """DHL Configuration response schema"""
    id_dhl_config: int
    id_carrier_api: int
    description: str
    shipper_account_number: str
    company_name: str
    city: str
    address: str
    postal_code: str
    country_code: str
    reference_person: str
    email: str
    phone: str
    default_weight: Decimal
    package_height: int
    package_width: int
    package_depth: int
    goods_description: Optional[str]
    label_format: LabelFormatEnum
    unit_of_measure: UnitOfMeasureEnum
    default_is_customs_declarable: bool
    default_incoterm: Optional[str]
    duties_account_number: Optional[str]
    payer_account_number: Optional[str]
    province_code: Optional[str]
    tax_id: Optional[str]
    pickup_is_requested: bool
    pickup_close_time: Optional[str]
    pickup_location: Optional[str]
    default_product_code_domestic: str
    default_product_code_international: str
    cod_enabled: bool
    cod_currency: Optional[str]
    
    model_config = {"from_attributes": True}


class DhlConfigurationUpdateSchema(BaseModel):
    """DHL Configuration update schema"""
    description: Optional[str] = Field(None, max_length=255)
    shipper_account_number: Optional[str] = Field(None, max_length=255)
    company_name: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    postal_code: Optional[str] = Field(None, max_length=20)
    country_code: Optional[str] = Field(None, max_length=2, pattern=r'^[A-Z]{2}$')
    reference_person: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50, pattern=r'^\+?[0-9]{10,15}$')
    default_weight: Optional[Decimal] = Field(None, gt=0)
    package_height: Optional[int] = Field(None, gt=0)
    package_width: Optional[int] = Field(None, gt=0)
    package_depth: Optional[int] = Field(None, gt=0)
    goods_description: Optional[str] = None
    label_format: Optional[LabelFormatEnum] = None
    unit_of_measure: Optional[UnitOfMeasureEnum] = None
    default_is_customs_declarable: Optional[bool] = None
    default_incoterm: Optional[str] = Field(None, max_length=3)
    duties_account_number: Optional[str] = Field(None, max_length=255)
    payer_account_number: Optional[str] = Field(None, max_length=255)
    province_code: Optional[str] = Field(None, max_length=50)
    tax_id: Optional[str] = Field(None, max_length=255)
    pickup_is_requested: Optional[bool] = None
    pickup_close_time: Optional[str] = Field(None, max_length=5, pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    pickup_location: Optional[str] = Field(None, max_length=255)
    default_product_code_domestic: Optional[str] = Field(None, max_length=100)
    default_product_code_international: Optional[str] = Field(None, max_length=100)
    cod_enabled: Optional[bool] = None
    cod_currency: Optional[str] = Field(None, max_length=3)
