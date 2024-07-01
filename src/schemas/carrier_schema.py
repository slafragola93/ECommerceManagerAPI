from typing import Optional
from pydantic import BaseModel, Field


class CarrierSchema(BaseModel):
    id_origin: Optional[int] = None
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


class ConfigDict:
    from_attributes = True
