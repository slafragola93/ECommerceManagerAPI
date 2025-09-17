from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel

from src.schemas import AddressSchema, CustomerSchema, ShippingSchema, SectionalSchema
from src.schemas.address_schema import AddressResponseSchema
from src.schemas.customer_schema import CustomerResponseSchema
from src.schemas.shipping_schema import ShippingResponseSchema
from src.schemas.sectional_schema import SectionalResponseSchema
from src.schemas.order_state_schema import OrderStateResponseSchema


class OrderSchema(BaseModel):
    address_delivery: int | AddressSchema = 0
    address_invoice: int | AddressSchema = 0
    customer: CustomerSchema | int = 0
    id_platform: Optional[int] = 0
    id_payment: Optional[int] = 0
    shipping: int | ShippingSchema | None = 0
    sectional: int | SectionalSchema = 0
    id_order_state: int
    id_origin: Optional[int] = 0
    is_invoice_requested: bool
    is_payed: Optional[int] = 0
    payment_date: Optional[datetime] = None
    total_weight: Optional[float] = None
    total_price: Optional[float] = None
    cash_on_delivery: Optional[float] = None

    class Config:
        orm_mode = True


class OrderUpdateSchema(BaseModel):
    """Schema per aggiornamenti parziali dell'ordine - tutti i campi sono opzionali e solo ID"""
    id_address_delivery: Optional[int] = None
    id_address_invoice: Optional[int] = None
    id_customer: Optional[int] = None
    id_platform: Optional[int] = None
    id_payment: Optional[int] = None
    id_shipping: Optional[int] = None
    id_sectional: Optional[int] = None
    id_order_state: Optional[int] = None
    id_origin: Optional[int] = None
    is_invoice_requested: Optional[bool] = None
    is_payed: Optional[int] = None
    payment_date: Optional[datetime] = None
    total_weight: Optional[float] = None
    total_price: Optional[float] = None
    cash_on_delivery: Optional[float] = None
    insured_value: Optional[float] = None
    privacy_note: Optional[str] = None
    general_note: Optional[str] = None
    delivery_date: Optional[datetime] = None

    class Config:
        orm_mode = True


class OrderResponseSchema(BaseModel):
    id_order: int
    id_origin: Optional[int]
    id_address_delivery: Optional[int]
    id_address_invoice: Optional[int]
    id_customer: Optional[int]
    id_platform: Optional[int]
    id_payment: Optional[int]
    id_shipping: Optional[int]
    id_sectional: Optional[int]
    id_order_state: int
    is_invoice_requested: bool
    is_payed: Optional[bool]
    payment_date: Optional[datetime]
    total_weight: Optional[float]
    total_price: Optional[float]
    cash_on_delivery: Optional[float]
    insured_value: Optional[float]
    privacy_note: Optional[str]
    general_note: Optional[str]
    delivery_date: Optional[datetime]
    date_add: datetime
    
    # Relazioni
    address_delivery: Optional[AddressResponseSchema] = None
    address_invoice: Optional[AddressResponseSchema] = None
    customer: Optional[CustomerResponseSchema] = None
    shipping: Optional[ShippingResponseSchema] = None
    sectional: Optional[SectionalResponseSchema] = None
    order_states: Optional[list[OrderStateResponseSchema]] = None

    class Config:
        from_attributes = True


class OrderIdSchema(BaseModel):
    """Schema per la risposta di get_order_by_id con relazioni popolate"""
    id_order: int
    id_origin: Optional[int]
    # Campi ID per compatibilità con i test
    id_address_delivery: Optional[int] = None
    id_address_invoice: Optional[int] = None
    id_customer: Optional[int] = None
    id_platform: Optional[int] = None
    id_payment: Optional[int] = None
    id_shipping: Optional[int] = None
    id_sectional: Optional[int] = None
    id_order_state: Optional[int] = None
    # Campi dati
    is_invoice_requested: bool
    is_payed: Optional[bool]
    payment_date: Optional[datetime]
    total_weight: Optional[float]
    total_price: Optional[float]
    cash_on_delivery: Optional[float]
    insured_value: Optional[float]
    privacy_note: Optional[str]
    general_note: Optional[str]
    delivery_date: Optional[datetime]
    date_add: datetime
    
    # Relazioni popolate
    address_delivery: Optional[dict] = None
    address_invoice: Optional[dict] = None
    customer: Optional[dict] = None
    shipping: Optional[dict] = None
    sectional: Optional[dict] = None
    order_states: Optional[list[dict]] = None

    class Config:
        from_attributes = True


class AllOrderResponseSchema(BaseModel):
    orders: list[OrderIdSchema]
    total: int
    page: int
    limit: int

    class Config:
        from_attributes = True
