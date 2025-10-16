from typing import Optional, List, Union
from pydantic import BaseModel, Field, validator
import json
from .carrier_api_schema import CarrierApiResponseSchema


class CarrierAssignmentSchema(BaseModel):
    id_carrier_api: int = Field(..., gt=0, description="ID del carrier API da assegnare")
    postal_codes: Optional[str] = Field(None, max_length=1000, description="Lista di codici postali separati da virgola")
    countries: Optional[str] = Field(None, max_length=1000, description="Lista di ID paesi separati da virgola")
    origin_carriers: Optional[str] = Field(None, max_length=1000, description="Lista di ID carrier di origine separati da virgola")
    min_weight: Optional[float] = Field(None, ge=0, description="Peso minimo per l'assegnazione")
    max_weight: Optional[float] = Field(None, ge=0, description="Peso massimo per l'assegnazione")

    @validator('postal_codes')
    def validate_postal_codes(cls, v):
        if v is not None and v.strip():
            # Verifica che sia una lista di codici postali validi
            codes = [code.strip() for code in v.split(',') if code.strip()]
            for code in codes:
                if not code.isdigit() or len(code) < 3 or len(code) > 10:
                    raise ValueError(f"Codice postale non valido: {code}")
        return v

    @validator('countries')
    def validate_countries(cls, v):
        if v is not None and v.strip():
            # Verifica che sia una lista di ID numerici
            countries = [country.strip() for country in v.split(',') if country.strip()]
            for country in countries:
                if not country.isdigit():
                    raise ValueError(f"ID paese non valido: {country}")
        return v

    @validator('origin_carriers')
    def validate_origin_carriers(cls, v):
        if v is not None and v.strip():
            # Verifica che sia una lista di ID numerici
            carriers = [carrier.strip() for carrier in v.split(',') if carrier.strip()]
            for carrier in carriers:
                if not carrier.isdigit():
                    raise ValueError(f"ID carrier di origine non valido: {carrier}")
        return v

    @validator('max_weight')
    def validate_weight_range(cls, v, values):
        if v is not None and 'min_weight' in values and values['min_weight'] is not None:
            if v < values['min_weight']:
                raise ValueError("Il peso massimo deve essere maggiore o uguale al peso minimo")
        return v


class CarrierAssignmentUpdateSchema(BaseModel):
    id_carrier_api: Optional[int] = Field(None, gt=0)
    postal_codes: Optional[str] = Field(None, max_length=1000)
    countries: Optional[str] = Field(None, max_length=1000)
    origin_carriers: Optional[str] = Field(None, max_length=1000)
    min_weight: Optional[float] = Field(None, ge=0)
    max_weight: Optional[float] = Field(None, ge=0)

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

    @validator('origin_carriers')
    def validate_origin_carriers(cls, v):
        if v is not None and v.strip():
            carriers = [carrier.strip() for carrier in v.split(',') if carrier.strip()]
            for carrier in carriers:
                if not carrier.isdigit():
                    raise ValueError(f"ID carrier di origine non valido: {carrier}")
        return v

    @validator('max_weight')
    def validate_weight_range(cls, v, values):
        if v is not None and 'min_weight' in values and values['min_weight'] is not None:
            if v < values['min_weight']:
                raise ValueError("Il peso massimo deve essere maggiore o uguale al peso minimo")
        return v


class CarrierAssignmentResponseSchema(BaseModel):
    id_carrier_assignment: int
    id_carrier_api: int
    postal_codes: Optional[str]
    countries: Optional[str]
    origin_carriers: Optional[str]
    min_weight: Optional[float]
    max_weight: Optional[float]
    carrier_api: Optional[CarrierApiResponseSchema] = None  # Popolato dalla repository

    class Config:
        from_attributes = True


class AllCarrierAssignmentsResponseSchema(BaseModel):
    carrier_assignments: List[CarrierAssignmentResponseSchema]
    total: int
    page: int
    limit: int


class CarrierAssignmentIdSchema(BaseModel):
    id_carrier_assignment: int
    id_carrier_api: int
    postal_codes: Optional[str]
    countries: Optional[str]
    origin_carriers: Optional[str]
    min_weight: Optional[float]
    max_weight: Optional[float]
    carrier_api: Optional[dict] = None

    class Config:
        from_attributes = True
