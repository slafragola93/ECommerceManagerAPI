from typing import Optional, List
from pydantic import BaseModel, Field, validator
from .carrier_api_schema import CarrierApiResponseSchema


class CarrierPriceSchema(BaseModel):
    id_carrier_api: int = Field(..., gt=0, description="ID del carrier API")
    postal_codes: Optional[str] = Field(None, max_length=1000, description="Lista di codici postali separati da virgola")
    countries: Optional[str] = Field(None, max_length=1000, description="Lista di ID paesi separati da virgola")
    min_weight: Optional[float] = Field(None, ge=0, description="Peso minimo")
    max_weight: Optional[float] = Field(None, ge=0, description="Peso massimo")
    price_with_tax: Optional[float] = Field(None, ge=0, description="Prezzo con IVA del corriere")

    @validator('postal_codes')
    def validate_postal_codes(cls, v):
        if v is not None and v.strip():
            codes = [code.strip() for code in v.split(',') if code.strip()]
            for code in codes:
                if not code.isdigit() or len(code) < 3 or len(code) > 10:
                    raise ValueError(f"Codice postale non valido: {code}")
        return v

    @validator('countries')
    def validate_countries(cls, v):
        if v is not None and v.strip():
            countries = [country.strip() for country in v.split(',') if country.strip()]
            for country in countries:
                if not country.isdigit():
                    raise ValueError(f"ID paese non valido: {country}")
        return v

    @validator('max_weight')
    def validate_weight_range(cls, v, values):
        if v is not None and 'min_weight' in values and values['min_weight'] is not None:
            if v < values['min_weight']:
                raise ValueError("Il peso massimo deve essere maggiore o uguale al peso minimo")
        return v


class CarrierPriceUpdateSchema(BaseModel):
    id_carrier_api: Optional[int] = Field(None, gt=0)
    postal_codes: Optional[str] = Field(None, max_length=1000)
    countries: Optional[str] = Field(None, max_length=1000)
    min_weight: Optional[float] = Field(None, ge=0)
    max_weight: Optional[float] = Field(None, ge=0)
    price_with_tax: Optional[float] = Field(None, ge=0)

    @validator('postal_codes')
    def validate_postal_codes(cls, v):
        if v is not None and v.strip():
            codes = [code.strip() for code in v.split(',') if code.strip()]
            for code in codes:
                if not code.isdigit() or len(code) < 3 or len(code) > 10:
                    raise ValueError(f"Codice postale non valido: {code}")
        return v

    @validator('countries')
    def validate_countries(cls, v):
        if v is not None and v.strip():
            countries = [country.strip() for country in v.split(',') if country.strip()]
            for country in countries:
                if not country.isdigit():
                    raise ValueError(f"ID paese non valido: {country}")
        return v

    @validator('max_weight')
    def validate_weight_range(cls, v, values):
        if v is not None and 'min_weight' in values and values['min_weight'] is not None:
            if v < values['min_weight']:
                raise ValueError("Il peso massimo deve essere maggiore o uguale al peso minimo")
        return v


class CarrierPriceResponseSchema(BaseModel):
    id_carrier_price: int
    id_carrier_api: int
    postal_codes: Optional[str]
    countries: Optional[str]
    min_weight: Optional[float]
    max_weight: Optional[float]
    price_with_tax: Optional[float]
    carrier_api: Optional[CarrierApiResponseSchema] = None

    @validator('min_weight', 'max_weight', 'price_with_tax', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)

    class Config:
        from_attributes = True

