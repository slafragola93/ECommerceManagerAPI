from typing import Optional
from pydantic import BaseModel, Field


class TaxSchema(BaseModel):
    id_country: Optional[int] = None
    is_default: Optional[int] = 0
    name: str = Field(..., min_length=5, max_length=200)
    note: Optional[str] = ""
    percentage: Optional[int] = 0
    electronic_code: Optional[str]


class TaxResponseSchema(BaseModel):
    id_tax: int
    id_country: Optional[int]
    is_default: int
    name: str
    note: Optional[str]
    percentage: int
    electronic_code: Optional[str]


class AllTaxesResponseSchema(BaseModel):
    taxes: list[TaxResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
