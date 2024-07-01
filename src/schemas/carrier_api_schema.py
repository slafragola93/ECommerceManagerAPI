from typing import Optional
from pydantic import BaseModel, Field


class CarrierApiSchema(BaseModel):
    name: str = Field(..., max_length=200)
    account_number: int = Field(..., gt=0)
    password: str = Field(..., max_length=15)
    site_id: str = Field(..., max_length=200)
    national_service: str = Field(..., max_length=10)
    international_service: str = Field(..., max_length=10)
    is_active: Optional[bool] = True
    api_key: Optional[str] = None


class CarrierApiResponseSchema(BaseModel):
    id_carrier_api: int
    name: str
    account_number: int
    # password: str
    site_id: str
    national_service: str
    international_service: str
    is_active: bool
    api_key: str


class AllCarriersApiResponseSchema(BaseModel):
    carriers: list[CarrierApiResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
