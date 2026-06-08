from typing import Any, List, Optional
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

TAX_PERCENTAGE_QUANTUM = Decimal("0.01")


def coerce_optional_int(value: Any) -> Optional[int]:
    """Normalizza id_country (e campi analoghi) a int o None per l'API."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("id_country must be an integer or null")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise ValueError("id_country must be an integer or null")
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        return int(stripped)
    raise ValueError("id_country must be an integer or null")


def coerce_tax_percentage(value: Any) -> Decimal:
    """Normalizza percentage a Decimal(5,2) per input API e serializzazione."""
    if value is None or value == "":
        return Decimal("0.00")
    if isinstance(value, bool):
        raise ValueError("percentage must be a number")
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("percentage must be a number") from exc
    if dec < 0 or dec > 100:
        raise ValueError("percentage must be between 0 and 100")
    return dec.quantize(TAX_PERCENTAGE_QUANTUM)


class TaxSchema(BaseModel):
    id_country: Optional[int] = None
    is_default: Optional[int] = 0
    name: str = Field(..., min_length=5, max_length=200)
    note: Optional[str] = ""
    percentage: Optional[Decimal] = Field(default=Decimal("0.00"), ge=0, le=100)
    electronic_code: Optional[str] = ""

    @field_validator("id_country", mode="before")
    @classmethod
    def normalize_id_country(cls, value: Any) -> Optional[int]:
        return coerce_optional_int(value)

    @field_validator("percentage", mode="before")
    @classmethod
    def normalize_percentage(cls, value: Any) -> Decimal:
        return coerce_tax_percentage(value)


class TaxResponseSchema(BaseModel):
    id_tax: int
    id_country: Optional[int] = None
    is_default: int
    name: str
    note: Optional[str] = None
    percentage: Decimal = Field(..., ge=0, le=100)
    electronic_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("id_country", mode="before")
    @classmethod
    def normalize_id_country(cls, value: Any) -> Optional[int]:
        return coerce_optional_int(value)

    @field_validator("percentage", mode="before")
    @classmethod
    def normalize_percentage(cls, value: Any) -> Decimal:
        return coerce_tax_percentage(value)

    @field_serializer("percentage")
    def serialize_percentage(self, value: Decimal) -> float:
        """JSON number (es. 25.5) per compatibilità FE."""
        return float(value)


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


def serialize_tax_response(tax: Any) -> dict:
    """Serializza un Tax ORM/dict con tipi API coerenti (id_country int|null)."""
    return TaxResponseSchema.model_validate(tax).model_dump(mode="json")


def serialize_taxes_response(taxes: List[Any]) -> List[dict]:
    return [serialize_tax_response(t) for t in taxes]
