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


class DDTCreatePartialItemSchema(BaseModel):
    """Schema per singolo articolo in creazione DDT parziale"""
    id_order_detail: int = Field(..., gt=0, description="ID dell'articolo ordine")
    quantity: int = Field(..., gt=0, description="Quantità da includere nel DDT")


class DDTCreatePartialRequestSchema(BaseModel):
    """Schema per richiesta creazione DDT parziale da order_detail"""
    articoli: List[DDTCreatePartialItemSchema] = Field(..., min_items=1, description="Lista di articoli da includere nel DDT")


class DDTCreatePartialResponseSchema(BaseModel):
    """Schema per risposta creazione DDT parziale"""
    success: bool
    message: str
    ddt: Optional[DDTResponseSchema] = None


class DDTListRequestSchema(BaseModel):
    """Schema per filtri lista DDT"""
    search: Optional[str] = None
    sectionals_ids: Optional[str] = None
    payments_ids: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    page: int = Field(1, ge=1)
    limit: int = Field(100, ge=1, le=1000)


class DDTListItemSchema(BaseModel):
    """Schema per elemento lista DDT essenziale"""
    id_order_document: int
    document_number: int
    date_add: Optional[datetime] = None
    customer: Optional[dict] = None  # Solo id e nome
    articoli: List[dict] = Field(default_factory=list)  # Lista essenziale articoli


class DDTListResponseSchema(BaseModel):
    """Schema per risposta lista DDT essenziali"""
    ddt_list: List[DDTListItemSchema]
    total: int
    page: int
    limit: int


class DDTCreateRequestSchema(BaseModel):
    """Schema per creazione DDT normale"""
    id_order: Optional[int] = Field(None, gt=0, description="ID ordine collegato (opzionale)")
    id_customer: Optional[int] = Field(None, gt=0)
    id_address_delivery: Optional[int] = Field(None, gt=0)
    id_address_invoice: Optional[int] = Field(None, gt=0)
    id_sectional: Optional[int] = Field(None, gt=0)
    id_shipping: Optional[int] = Field(None, gt=0)
    id_payment: Optional[int] = Field(None, gt=0)
    is_invoice_requested: Optional[bool] = False
    note: Optional[str] = Field(None, max_length=200)


class DDTCreateResponseSchema(BaseModel):
    """Schema per risposta creazione DDT normale"""
    success: bool
    message: str
    ddt: Optional[DDTResponseSchema] = None


class DDTMergeRequestSchema(BaseModel):
    """Schema per richiesta accorpamento articolo a DDT"""
    id_order_document: int = Field(..., gt=0, description="ID DDT esistente")
    id_order_detail: int = Field(..., gt=0, description="ID articolo ordine da aggiungere")
    quantity: int = Field(..., gt=0, description="Quantità da aggiungere")


class DDTMergeResponseSchema(BaseModel):
    """Schema per risposta accorpamento DDT"""
    success: bool
    message: str
    ddt: Optional[DDTResponseSchema] = None