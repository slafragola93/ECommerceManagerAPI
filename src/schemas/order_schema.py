from datetime import datetime
from typing import Optional, Union, List

from pydantic import BaseModel, ConfigDict, Field, validator

from src.schemas import AddressSchema, CustomerSchema, ShippingSchema, SectionalSchema
from src.schemas.address_schema import AddressResponseSchema
from src.schemas.customer_schema import CustomerResponseSchema
from src.schemas.order_detail_schema import OrderDetailSchema
from src.schemas.shipping_schema import ShippingResponseSchema
from src.schemas.sectional_schema import SectionalResponseSchema
from src.schemas.order_state_schema import OrderStateResponseSchema


class OrderHistorySchema(BaseModel):
    """Elemento di cronologia ordine: stato e data evento"""
    state: str
    data: datetime

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class OrderSchema(BaseModel):
    address_delivery: int | AddressSchema = 0
    address_invoice: int | AddressSchema = 0
    customer: CustomerSchema | int = 0
    id_platform: Optional[int] = 0
    id_payment: Optional[int] = 0
    id_carrier: Optional[int] = 0
    shipping: int | ShippingSchema | None = 0
    sectional: int | SectionalSchema = 0
    id_order_state: int
    id_origin: Optional[int] = 0
    reference: Optional[str] = None
    is_invoice_requested: bool
    is_payed: Optional[int] = 0
    payment_date: Optional[datetime] = None
    total_weight: Optional[float] = None
    total_price_with_tax: float  # Required (ex total_with_tax, ex total_paid)
    total_price_net: Optional[float] = None  # ex total_without_tax
    total_discounts: Optional[float] = 0.0
    cash_on_delivery: Optional[float] = None
    order_details: Optional[list[OrderDetailSchema]] = None

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class OrderUpdateSchema(BaseModel):
    """Schema per aggiornamenti parziali dell'ordine - tutti i campi sono opzionali e solo ID"""
    id_address_delivery: Optional[int] = None
    id_address_invoice: Optional[int] = None
    id_customer: Optional[int] = None
    id_platform: Optional[int] = None
    id_payment: Optional[int] = None
    id_carrier: Optional[int] = None
    id_shipping: Optional[int] = None
    id_sectional: Optional[int] = None
    id_order_state: Optional[int] = None
    id_origin: Optional[int] = None
    reference: Optional[str] = None
    is_invoice_requested: Optional[bool] = None
    is_payed: Optional[int] = None
    payment_date: Optional[datetime] = None
    total_weight: Optional[float] = None
    total_price_with_tax: Optional[float] = None  # ex total_with_tax, ex total_paid
    total_price_net: Optional[float] = None  # ex total_without_tax
    total_discounts: Optional[float] = None
    cash_on_delivery: Optional[float] = None
    insured_value: Optional[float] = None
    privacy_note: Optional[str] = None
    general_note: Optional[str] = None
    delivery_date: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class OrderSimpleResponseSchema(BaseModel):
    """Schema per risposta semplice degli ordini (solo ID)"""
    id_order: int
    id_origin: Optional[int]
    reference: Optional[str]
    id_address_delivery: Optional[int]
    id_address_invoice: Optional[int]
    id_customer: Optional[int]
    id_platform: Optional[int]
    id_payment: Optional[int]
    id_carrier: Optional[int]
    id_shipping: Optional[int]
    id_sectional: Optional[int]
    id_order_state: int
    is_invoice_requested: bool
    is_payed: Optional[bool]
    payment_date: Optional[datetime]
    total_weight: Optional[float]
    total_price_with_tax: Optional[float]  # ex total_with_tax, ex total_paid
    total_price_net: Optional[float]  # ex total_without_tax
    total_discounts: Optional[float]
    cash_on_delivery: Optional[float]
    insured_value: Optional[float]
    privacy_note: Optional[str]
    general_note: Optional[str]
    delivery_date: Optional[datetime]
    date_add: Optional[datetime] = None

    @validator('total_weight', 'total_price_with_tax', 'total_price_net', 'total_discounts', 'cash_on_delivery', 'insured_value', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class OrderResponseSchema(BaseModel):
    """Schema per risposta completa degli ordini (con dettagli)"""
    id_order: int
    id_origin: Optional[int]
    reference: Optional[str]
    id_address_delivery: Optional[int]
    id_address_invoice: Optional[int]
    id_customer: Optional[int]
    id_platform: Optional[int]
    id_payment: Optional[int]
    id_carrier: Optional[int]
    id_shipping: Optional[int]
    id_sectional: Optional[int]
    id_order_state: int
    is_invoice_requested: bool
    is_payed: Optional[bool]
    payment_date: Optional[datetime]
    total_weight: Optional[float]
    total_price_with_tax: Optional[float]  # ex total_with_tax, ex total_paid
    total_price_net: Optional[float]  # ex total_without_tax
    total_discounts: Optional[float]
    cash_on_delivery: Optional[float]
    insured_value: Optional[float]
    privacy_note: Optional[str]
    general_note: Optional[str]
    delivery_date: Optional[datetime]
    date_add: Optional[datetime] = None
    updated_at: Optional[str] = None  # Formato: DD-MM-YYYY hh:mm:ss
    
    # Relazioni popolate
    address_delivery: Optional[AddressResponseSchema] = None
    address_invoice: Optional[AddressResponseSchema] = None
    customer: Optional[CustomerResponseSchema] = None
    shipping: Optional[ShippingResponseSchema] = None
    sectional: Optional[SectionalResponseSchema] = None
    order_states: Optional[list[OrderStateResponseSchema]] = None
    order_details: Optional[list] = None 
    order_history: Optional[list[OrderHistorySchema]] = None

    @validator('total_weight', 'total_price_with_tax', 'total_price_net', 'total_discounts', 'cash_on_delivery', 'insured_value', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class OrderIdSchema(BaseModel):
    """Schema per la risposta di get_order_by_id con relazioni popolate"""
    id_order: int
    id_origin: Optional[int]
    reference: Optional[str]
    # Campi dati
    is_invoice_requested: bool
    is_payed: Optional[bool]
    payment_date: Optional[datetime]
    total_weight: Optional[float]
    total_price_with_tax: Optional[float]  # ex total_with_tax, ex total_paid
    total_price_net: Optional[float]  # ex total_without_tax
    total_discounts: Optional[float]
    cash_on_delivery: Optional[float]
    insured_value: Optional[float]
    privacy_note: Optional[str]
    general_note: Optional[str]
    delivery_date: Optional[datetime]
    date_add: Optional[datetime] = None
    
    # Relazioni popolate
    address_delivery: Optional[dict] = None
    address_invoice: Optional[dict] = None
    payment: Optional[dict] = None
    platform: Optional[dict] = None
    order_states: Optional[dict] = None
    customer: Optional[dict] = None
    shipping: Optional[dict] = None
    sectional: Optional[dict] = None
    order_states: Optional[list[dict]] = None
    order_details: Optional[list] = None 
    order_packages: Optional[list] = None

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class AllOrderResponseSchema(BaseModel):
    orders: list[OrderSimpleResponseSchema]
    total: int
    page: int
    limit: int

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class OrderStatusUpdateItem(BaseModel):
    """Schema per singolo aggiornamento stato ordine in bulk update."""
    id_order: int = Field(gt=0, description="ID dell'ordine da aggiornare")
    id_order_state: int = Field(gt=0, description="Nuovo stato dell'ordine")

    model_config = ConfigDict(from_attributes=True, extra='forbid')


# BulkOrderStatusUpdateSchema è semplicemente una lista di OrderStatusUpdateItem
BulkOrderStatusUpdateSchema = List[OrderStatusUpdateItem]


class OrderStatusUpdateResult(BaseModel):
    """Risultato di un aggiornamento stato ordine riuscito."""
    id_order: int
    old_state_id: int
    new_state_id: int

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class OrderStatusUpdateError(BaseModel):
    """Errore di un aggiornamento stato ordine fallito."""
    id_order: int
    error: str
    reason: str

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class BulkOrderStatusUpdateResponseSchema(BaseModel):
    """Schema per risposta aggiornamento massivo stati ordini."""
    successful: List[OrderStatusUpdateResult] = Field(
        default_factory=list,
        description="Lista di aggiornamenti riusciti"
    )
    failed: List[OrderStatusUpdateError] = Field(
        default_factory=list,
        description="Lista di aggiornamenti falliti"
    )
    summary: dict = Field(
        description="Riepilogo operazione: total, successful_count, failed_count"
    )

    model_config = ConfigDict(from_attributes=True, extra='forbid')
