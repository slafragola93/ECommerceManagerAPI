from typing import Optional
from pydantic import BaseModel, Field


class ShippingSchema(BaseModel):
    id_carrier_api: int = Field(..., gt=0)
    id_shipping_state: int = Field(..., gt=0)
    id_tax: int = Field(..., gt=0)
    tracking: Optional[str] = None
    weight: float
    price_tax_incl: float
    price_tax_excl: float
    shipping_message: Optional[str] = None


class ShippingResponseSchema(BaseModel):
    id_carrier_api: int
    id_shipping_state: int
    id_tax: int
    tracking: str | None
    weight: float
    price_tax_incl: float
    price_tax_excl: float
    shipping_message: Optional[str] = None


class ConfigDict:
    from_attributes = True
