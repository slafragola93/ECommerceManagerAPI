from typing import Optional, List, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from .customer_schema import CustomerSchema
from .address_schema import AddressSchema


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


class ArticoloPreventivoSchema(BaseModel):
    """Schema per articolo in preventivo (OrderDetail)"""
    id_product: Optional[int] = None  # Se articolo esistente
    product_name: Optional[str] = Field(None, max_length=100)
    product_reference: Optional[str] = Field(None, max_length=100)
    product_price: Optional[float] = Field(0.0, gt=0)
    product_weight: Optional[float] = Field(0.0, ge=0)
    product_qty: int = Field(1, gt=0)  # Integer come nel modello
    id_tax: int = Field(..., gt=0)  # Sempre obbligatorio
    reduction_percent: Optional[float] = Field(0.0, ge=0)  # Sconto percentuale
    reduction_amount: Optional[float] = Field(0.0, ge=0)  # Sconto importo
    rda: Optional[str] = Field(None, max_length=10)  # RDA
    # Campi calcolati automaticamente
    prezzo_totale_riga: Optional[float] = None
    aliquota_iva: Optional[float] = None
    
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
    note: Optional[str] = None
    articoli: List[ArticoloPreventivoSchema] = Field(default_factory=list)


class PreventivoUpdateSchema(BaseModel):
    """Schema per modifica preventivo"""
    reference: Optional[str] = Field(None, max_length=32)
    note: Optional[str] = None


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


class PreventivoResponseSchema(BaseModel):
    """Schema per risposta preventivo"""
    id_order_document: int
    document_number: str
    id_customer: int
    customer_name: Optional[str] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    type_document: str
    total_imponibile: float
    total_iva: float
    total_finale: float
    date_add: datetime
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
