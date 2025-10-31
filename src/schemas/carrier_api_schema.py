from typing import Optional
from pydantic import BaseModel, Field
from src.models.carrier_api import CarrierTypeEnum


class CarrierApiSchema(BaseModel):
    name: str = Field(..., max_length=200)
    carrier_type: CarrierTypeEnum = Field(...)
    is_active: Optional[bool] = True
    api_key: Optional[str] = Field(None, max_length=200)
    
    # Generic authentication fields
    use_sandbox: Optional[bool] = False


class CarrierApiResponseSchema(BaseModel):
    id_carrier_api: int
    name: str
    carrier_type: CarrierTypeEnum
    is_active: bool
    api_key: Optional[str]
    
    # Generic authentication fields
    use_sandbox: Optional[bool]
    
    model_config = {"from_attributes": True}


class CarrierApiUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    is_active: Optional[bool] = None
    api_key: Optional[str] = Field(None, max_length=200)
    
    # Generic authentication fields
    use_sandbox: Optional[bool] = None


class AllCarriersApiResponseSchema(BaseModel):
    carriers: list[CarrierApiResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
