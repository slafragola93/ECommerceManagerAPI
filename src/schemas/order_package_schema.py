from typing import Optional
from pydantic import BaseModel, Field, validator


class OrderPackageSchema(BaseModel):

    id_order: Optional[int] = None
    id_order_document: Optional[int] = None
    height: float
    width: float
    depth: float
    weight: float
    length: float
    value: float = Field(default=0.0)


class OrderPackageResponseSchema(BaseModel):
    id_order_package: int
    id_order: Optional[int] = None
    id_order_document: Optional[int] = None
    height: float
    width: float
    depth: float
    weight: float
    length: float
    value: float
    
    @validator('height', 'width', 'depth', 'weight', 'length', 'value', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)
    
    model_config = {"from_attributes": True}


class AllOrderPackagesResponseSchema(BaseModel):
    order_packages: list[OrderPackageResponseSchema]
    total: int
    page: int
    limit: int
    
    model_config = {"from_attributes": True}
