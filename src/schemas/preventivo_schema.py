from typing import Optional, List, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from .customer_schema import CustomerSchema
from .address_schema import AddressSchema
from .shipping_schema import ShippingSchema
from .sectional_schema import SectionalSchema, SectionalResponseSchema
from .shipping_schema import ShippingResponseSchema


class CustomerField(BaseModel):
    """Campo customer che può essere ID o oggetto completo"""
    id: Optional[int] = Field(None, gt=0)
    data: Optional[CustomerSchema] = None
    
    @validator('id', 'data')
    def validate_customer_field(cls, v, values):
        """Valida che sia presente o id o data"""
        if not v and not values.get('data') and not values.get('id'):
            raise ValueError('Deve essere specificato o id o data per customer')
        return v


class AddressField(BaseModel):
    """Campo address che può essere ID o oggetto completo"""
    id: Optional[int] = Field(None, gt=0)
    data: Optional[AddressSchema] = None
    
    @validator('id', 'data')
    def validate_address_field(cls, v, values):
        """Valida che sia presente o id o data"""
        if not v and not values.get('data') and not values.get('id'):
            # Address è opzionale
            return v
        return v


class SectionalField(BaseModel):
    """Campo sectional che può essere ID o oggetto completo"""
    id: Optional[int] = Field(None, gt=0)
    data: Optional[SectionalSchema] = None
    
    @validator('id', 'data')
    def validate_sectional_field(cls, v, values):
        """Valida che sia presente o id o data"""
        if not v and not values.get('data') and not values.get('id'):
            # Sectional è opzionale
            return v
        return v


class ShippingField(BaseModel):
    """Campo shipping opzionale per preventivi"""
    price_tax_excl: float = Field(..., ge=0, description="Prezzo spedizione senza IVA")
    price_tax_incl: float = Field(..., ge=0, description="Prezzo spedizione con IVA")
    id_carrier_api: int = Field(..., gt=0, description="ID carrier API")
    id_tax: int = Field(..., gt=0, description="ID aliquota IVA per spedizione")
    shipping_message: Optional[str] = Field(None, max_length=200)


class ArticoloPreventivoSchema(BaseModel):
    """Schema per articolo in preventivo (OrderDetail)"""
    id_order_detail: Optional[int]  = None
    id_product: Optional[int] = None  # Se articolo esistente
    product_name: Optional[str] = Field(None, max_length=100)
    product_reference: Optional[str] = Field(None, max_length=100)
    product_price: Optional[float] = Field(0.0, gt=0)
    product_weight: Optional[float] = Field(0.0, ge=0)
    product_qty: int = Field(1, gt=0)  # Integer come nel modello
    id_tax: int = Field(..., gt=0)  # Sempre obbligatorio
    reduction_percent: Optional[float] = Field(0.0, ge=0)  # Sconto percentuale
    reduction_amount: Optional[float] = Field(0.0, ge=0)  # Sconto importo
    
    @validator('product_name', 'product_reference', 'product_price', 'product_qty')
    def validate_fields_when_no_product(cls, v, values):
        """Valida che i campi siano presenti quando non c'è id_product"""
        if not values.get('id_product') and not v:
            raise ValueError('I campi product_name, product_reference, product_price e product_qty sono obbligatori quando non viene specificato id_product')
        return v


class PreventivoCreateSchema(BaseModel):
    """Schema per creazione preventivo"""
    customer: CustomerField = Field(..., description="Customer (ID o oggetto completo)")
    address_delivery: AddressField = Field(..., description="Address delivery (ID o oggetto completo) - obbligatorio")
    address_invoice: Optional[AddressField] = Field(None, description="Address invoice (ID o oggetto completo) - se non specificato usa address_delivery")
    sectional: Optional[SectionalField] = Field(None, description="Sezionale (ID o oggetto completo) - se esiste un sectional con lo stesso nome viene riutilizzato")
    shipping: Optional[ShippingField] = Field(None, description="Dati spedizione (opzionale)")
    is_invoice_requested: Optional[bool] = Field(False, description="Se richiedere fattura")
    note: Optional[str] = None
    articoli: List[ArticoloPreventivoSchema] = Field(default_factory=list)


class PreventivoUpdateSchema(BaseModel):
    """Schema per modifica preventivo"""
    # Campi che possono essere modificati
    id_order: Optional[int] = Field(None, gt=0)
    id_tax: Optional[int] = Field(None, gt=0)
    id_address_delivery: Optional[int] = Field(None, gt=0)
    id_address_invoice: Optional[int] = Field(None, gt=0)
    id_customer: Optional[int] = Field(None, gt=0)
    id_sectional: Optional[int] = Field(None, gt=0)
    id_shipping: Optional[int] = Field(None, gt=0)
    is_invoice_requested: Optional[bool] = None
    note: Optional[str] = Field(None, max_length=200)
    
    # Campi NON modificabili (esclusi dallo schema):
    # - document_number (generato automaticamente)
    # - type_document (sempre "preventivo")
    # - total_weight (calcolato automaticamente)
    # - total_price_with_tax (calcolato automaticamente)
    # - date_add (data di creazione, immutabile)


class ArticoloPreventivoUpdateSchema(BaseModel):
    """Schema per modifica articolo in preventivo (OrderDetail)"""
    product_name: Optional[str] = Field(None, max_length=100)
    product_reference: Optional[str] = Field(None, max_length=100)
    product_price: Optional[float] = Field(None, gt=0)
    product_weight: Optional[float] = Field(None, ge=0)
    product_qty: Optional[int] = Field(None, gt=0)  # Integer come nel modello
    id_tax: Optional[int] = Field(None, gt=0)
    reduction_percent: Optional[float] = Field(None, ge=0)  # Sconto percentuale
    reduction_amount: Optional[float] = Field(None, ge=0)  # Sconto importo
    rda: Optional[str] = Field(None, max_length=10)  # RDA


class PreventivoShipmentSchema(BaseModel):
    tax_rate: float
    weight: float
    price_tax_incl: float
    price_tax_excl: float
    shipping_message: Optional[str] = None


class PreventivoResponseSchema(BaseModel):
    """Schema per risposta preventivo"""
    id_order_document: int
    document_number: str
    id_customer: int
    sectional: Optional[SectionalResponseSchema] = None
    shipping: Optional[PreventivoShipmentSchema] = None
    customer_name: Optional[str] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    type_document: str
    total_imponibile: float
    total_iva: float
    total_finale: float
    date_add: Optional[datetime] = None
    updated_at: datetime
    articoli: List[ArticoloPreventivoSchema] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ConvertiPreventivoSchema(BaseModel):
    """Schema per conversione preventivo in ordine"""
    id_address_delivery: Optional[int] = None
    id_address_invoice: Optional[int] = None
    payment_method: Optional[str] = None
    note: Optional[str] = None


class PreventivoListResponseSchema(BaseModel):
    """Schema per lista preventivi"""
    preventivi: List[PreventivoResponseSchema]
    total: int
    page: int
    limit: int
