from typing import Optional
from pydantic import BaseModel, Field, validator


class ShippingSchema(BaseModel):
    id_carrier_api: Optional[int] = Field(None, gt=0)
    id_shipping_state: int = Field(..., gt=0)
    id_tax: Optional[int] = Field(default=1, gt=0)  # Default a 1 se non specificato
    tracking: Optional[str] = None
    weight: Optional[float] = Field(default=0.0, ge=0)
    price_tax_incl: float
    price_tax_excl: float
    shipping_message: Optional[str] = None


class ShippingResponseSchema(BaseModel):
    id_carrier_api: Optional[int] = None
    id_shipping_state: int
    id_tax: int
    tracking: str | None
    weight: float
    price_tax_incl: float
    price_tax_excl: float
    shipping_message: Optional[str] = None
    
    @validator('weight', 'price_tax_incl', 'price_tax_excl', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)


class AllShippingResponseSchema(BaseModel):
    shippings: list[ShippingResponseSchema]
    total: int
    page: int
    limit: int

    class ConfigDict:
        from_attributes = True
