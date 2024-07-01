from typing import Optional
from pydantic import BaseModel, Field


class CountrySchema(BaseModel):

    name: str = Field(..., max_length=200)
    iso_code: str = Field(..., min_length=2, max_length=5)


class CountryResponseSchema(BaseModel):
    id_country: int
    name: str
    iso_code: str


class AllCountryResponseSchema(BaseModel):
    countries: list[CountryResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
