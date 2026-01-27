from typing import Optional
from pydantic import BaseModel, Field, validator


class CarrierSchema(BaseModel):
    id_origin: Optional[int] = None
    id_store: Optional[int] = None
    name: str = Field(..., max_length=200)


class CarrierResponseSchema(BaseModel):
    id_carrier: int
    id_origin: int
    name: str


class AllCarriersResponseSchema(BaseModel):
    carriers: list[CarrierResponseSchema]
    total: int
    page: int
    limit: int


class CarrierPriceResponseSchema(BaseModel):
    price_with_tax: float
    price_net: float
    id_tax: int

    @validator('price_with_tax', 'price_net', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)


class ConfigDict:
    from_attributes = True
