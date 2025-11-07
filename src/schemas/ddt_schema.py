from typing import Optional, List
from pydantic import BaseModel, Field, validator
from datetime import datetime


class DDTDetailSchema(BaseModel):
    """Schema per dettaglio DDT (articolo)"""
    id_order_detail: int
    id_product: Optional[int] = None
    product_name: str
    product_reference: str
    product_qty: int = Field(..., ge=1)
    product_price: float = Field(..., ge=0)
    product_weight: Optional[float] = Field(0.0, ge=0)
    id_tax: int = Field(..., gt=0)
    reduction_percent: Optional[float] = Field(0.0, ge=0)
    reduction_amount: Optional[float] = Field(0.0, ge=0)
    
    @validator('product_price', 'product_weight', 'reduction_percent', 'reduction_amount', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)


class DDTDetailUpdateSchema(BaseModel):
    """Schema per aggiornamento dettaglio DDT"""
    product_name: Optional[str] = None
    product_reference: Optional[str] = None
    product_qty: Optional[int] = Field(None, ge=1)
    product_price: Optional[float] = Field(None, ge=0)
    product_weight: Optional[float] = Field(None, ge=0)
    id_tax: Optional[int] = Field(None, gt=0)
    reduction_percent: Optional[float] = Field(None, ge=0)
    reduction_amount: Optional[float] = Field(None, ge=0)


class DDTPackageSchema(BaseModel):
    """Schema per pacco DDT"""
    id_order_package: int
    height: float = Field(..., ge=0)
    width: float = Field(..., ge=0)
    depth: float = Field(..., ge=0)
    weight: float = Field(..., ge=0)
    value: float = Field(..., ge=0)


class DDTSenderSchema(BaseModel):
    """Schema per dati mittente DDT"""
    company_name: str
    address: str
    vat: str
    phone: str
    email: str
    logo_path: Optional[str] = None


class DDTResponseSchema(BaseModel):
    """Schema per risposta DDT completo"""
    id_order_document: int
    document_number: int
    type_document: str
    date_add: Optional[datetime] = None
    updated_at: datetime
    note: Optional[str] = None
    total_weight: float
    total_price_with_tax: float
    total_discount: float = Field(default=0.0, description="Sconto totale applicato al documento")
    apply_discount_to_tax_included: bool = Field(default=False, description="Se True, lo sconto è applicato al totale con IVA, altrimenti al totale senza IVA")
    
    # Dati ordine collegato
    id_order: int
    
    # Dati cliente
    customer: Optional[dict] = None
    
    # Dati indirizzi
    address_delivery: Optional[dict] = None
    address_invoice: Optional[dict] = None
    
    # Dati spedizione
    shipping: Optional[dict] = None
    
    # Dettagli (articoli)
    details: List[DDTDetailSchema] = []
    
    # Pacchi
    packages: List[DDTPackageSchema] = []
    
    # Mittente
    sender: DDTSenderSchema
    
    # Flag di modifica
    is_modifiable: bool
    
    @validator('total_weight', 'total_price_with_tax', 'total_discount', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)


class DDTGenerateRequestSchema(BaseModel):
    """Schema per richiesta generazione DDT"""
    id_order: int = Field(..., gt=0, description="ID dell'ordine da cui generare il DDT")


class DDTGenerateResponseSchema(BaseModel):
    """Schema per risposta generazione DDT"""
    success: bool
    message: str
    ddt: Optional[DDTResponseSchema] = None
