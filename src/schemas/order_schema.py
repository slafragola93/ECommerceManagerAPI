from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel

from src.schemas import AddressSchema, CustomerSchema, ShippingSchema, SectionalSchema


class OrderSchema(BaseModel):
    address_delivery: int | AddressSchema = 0
    address_invoice: int | AddressSchema = 0
    customer: CustomerSchema | int = None
    id_platform: Optional[int] = None
    id_payment: Optional[int] = None
    shipping: int | ShippingSchema | None = None
    sectional: int | SectionalSchema = None
    id_order_state: int
    id_origin: Optional[int] = None
    is_invoice_requested: bool
    is_payed: Optional[int] = None
    payment_date: Optional[datetime] = None
    total_weight: Optional[float] = None
    total_price: Optional[float] = None
    cash_on_delivery: Optional[float] = None

    class Config:
        orm_mode = True
