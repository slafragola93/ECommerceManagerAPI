from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


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

    model_config = ConfigDict(from_attributes=True)


class TaxCountryDefaultResponseSchema(TaxResponseSchema):
    """Tax default per paese con metadati paese (endpoint country-defaults)."""

    country_iso_code: Optional[str] = None
    country_name: Optional[str] = None


class AllTaxesResponseSchema(BaseModel):
    taxes: list[TaxResponseSchema]
    total: int
    page: int
    limit: int

    model_config = ConfigDict(from_attributes=True)


class CountryTaxDefaultsListResponseSchema(BaseModel):
    """Lista flat dei default IVA per paese."""

    country_defaults: List[TaxCountryDefaultResponseSchema]
    count: int
