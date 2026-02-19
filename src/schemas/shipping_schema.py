from typing import Optional, List
from pydantic import BaseModel, Field, validator


class ShippingSchema(BaseModel):
    id_carrier_api: Optional[int] = Field(None, gt=0)
    id_shipping_state: Optional[int] = Field(default=1, gt=0)  # Default a 1 se non specificato
    id_tax: Optional[int] = Field(default=1, gt=0)  # Default a 1 se non specificato
    tracking: Optional[str] = None
    weight: Optional[float] = Field(default=0.0, ge=0)
    price_tax_incl: float
    price_tax_excl: float
    customs_value: Optional[float] = Field(default=None, ge=0)
    shipping_message: Optional[str] = None


class ShippingUpdateSchema(BaseModel):
    """Schema per aggiornamento shipping con tutti i campi opzionali"""
    id_carrier_api: Optional[int] = Field(None, gt=0)
    id_shipping_state: Optional[int] = Field(None, gt=0)
    id_tax: Optional[int] = Field(None, gt=0)
    tracking: Optional[str] = None
    weight: Optional[float] = Field(None, ge=0)
    price_tax_incl: Optional[float] = None
    price_tax_excl: Optional[float] = None
    customs_value: Optional[float] = Field(None, ge=0)
    shipping_message: Optional[str] = None


class ShippingResponseSchema(BaseModel):
    id_carrier_api: Optional[int] = None
    id_shipping_state: int
    id_tax: Optional[int] = None
    tracking: str | None
    weight: float
    price_tax_incl: float
    price_tax_excl: float
    customs_value: Optional[float] = None
    shipping_message: Optional[str] = None
    
    @validator('weight', 'price_tax_incl', 'price_tax_excl', 'customs_value', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)
    class Config:
        from_attributes = True

class AllShippingResponseSchema(BaseModel):
    shippings: list[ShippingResponseSchema]
    total: int
    page: int
    limit: int

    class ConfigDict:
        from_attributes = True


# ==================== MULTI-SHIPMENT SCHEMAS ====================

class MultiShippingDocumentItemSchema(BaseModel):
    """Schema per item in creazione multi-shipment"""
    id_order_detail: int = Field(..., gt=0, description="ID dell'OrderDetail da spedire")
    quantity: int = Field(..., gt=0, description="Quantità da spedire")


class MultiShippingDocumentPackageSchema(BaseModel):
    """Schema per package in creazione multi-shipment"""
    height: Optional[float] = Field(None, ge=0, description="Altezza in cm")
    width: Optional[float] = Field(None, ge=0, description="Larghezza in cm")
    depth: Optional[float] = Field(None, ge=0, description="Profondità in cm")
    weight: float = Field(..., ge=0, description="Peso in kg")
    length: Optional[float] = Field(None, ge=0, description="Lunghezza in cm")


class MultiShippingDocumentCreateRequestSchema(BaseModel):
    """Schema per creazione documento spedizione multipla"""
    id_order: int = Field(..., gt=0, description="ID dell'ordine")
    id_carrier_api: int = Field(..., gt=0, description="ID del carrier API da usare")
    id_address_delivery: Optional[int] = Field(None, gt=0, description="ID indirizzo consegna (se None, usa quello dell'ordine)")
    items: List[MultiShippingDocumentItemSchema] = Field(..., min_items=1, description="Lista articoli da spedire")
    packages: Optional[List[MultiShippingDocumentPackageSchema]] = Field(None, description="Lista colli")
    shipping_message: Optional[str] = Field(None, max_length=500, description="Messaggio per la spedizione")


class MultiShippingDocumentItemResponseSchema(BaseModel):
    """Schema per item nella risposta multi-shipment"""
    id_order_detail: int
    product_name: str
    product_reference: Optional[str]
    quantity: int
    unit_price_net: float
    unit_price_with_tax: float
    total_price_net: float
    total_price_with_tax: float
    product_weight: float

    class ConfigDict:
        from_attributes = True


class MultiShippingDocumentPackageResponseSchema(BaseModel):
    """Schema per package nella risposta multi-shipment"""
    id_order_package: int
    height: Optional[float]
    width: Optional[float]
    depth: Optional[float]
    length: Optional[float]
    weight: float
    value: Optional[float]

    class ConfigDict:
        from_attributes = True


class MultiShippingDocumentResponseSchema(BaseModel):
    """Schema per risposta creazione documento spedizione multipla"""
    id_order_document: int
    id_shipping: int
    document_number: int
    type_document: str
    id_order: int
    id_carrier_api: int
    id_address_delivery: Optional[int]
    items: List[MultiShippingDocumentItemResponseSchema]
    packages: List[MultiShippingDocumentPackageResponseSchema]
    total_weight: Optional[float]
    total_price_with_tax: Optional[float]
    total_price_net: Optional[float]
    products_total_price_net: Optional[float]
    products_total_price_with_tax: Optional[float]
    shipping_message: Optional[str]
    date_add: str

    class ConfigDict:
        from_attributes = True


class OrderShipmentStatusItemSchema(BaseModel):
    """Schema per stato spedizione di un articolo"""
    id_order_detail: int
    product_name: str
    product_reference: Optional[str]
    total_qty: int
    shipped_qty: int
    remaining_qty: int
    fully_shipped: bool


class OrderShipmentStatusResponseSchema(BaseModel):
    """Schema per stato spedizione ordine"""
    order_id: int
    items: List[OrderShipmentStatusItemSchema]
    all_shipped: bool


class MultiShippingDocumentListItemSchema(BaseModel):
    """Schema per item in lista multi-shipments"""
    id_order_document: int
    id_shipping: int
    document_number: int
    id_carrier_api: Optional[int]
    total_weight: Optional[float]
    date_add: str
    items_count: int
    packages_count: int

    class ConfigDict:
        from_attributes = True


class MultiShippingDocumentListResponseSchema(BaseModel):
    """Schema per lista multi-shipments"""
    order_id: int
    shipments: List[MultiShippingDocumentListItemSchema]
    total: int
