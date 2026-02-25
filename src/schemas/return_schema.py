"""
Schemi per la gestione dei resi
"""
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime

from src.schemas.address_schema import AddressResponseSchema
from src.schemas.customer_schema import CustomerResponseSchema
from src.schemas.payment_schema import PaymentResponseSchema
from src.schemas.shipping_schema import ShippingResponseSchema


class ReturnItemSchema(BaseModel):
    """Schema per un singolo articolo da restituire"""
    id_order_detail: int = Field(..., description="ID del dettaglio ordine")
    quantity: int = Field(..., gt=0, description="Quantità da restituire")
    unit_price: Optional[float] = Field(None, gt=0, description="Prezzo unitario (se None, usa quello dell'order_detail)")
    id_tax:int = Field(..., gt=0, description="ID della tassa applicata")
    
    @validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError('La quantità deve essere maggiore di zero')
        return v


class ReturnCreateSchema(BaseModel):
    """Schema per la creazione di un reso"""
    order_details: List[ReturnItemSchema] = Field(..., description="Lista degli articoli da restituire")
    includes_shipping: bool = Field(False, description="Se includere le spese di spedizione")
    note: Optional[str] = Field(None, description="Note aggiuntive per il reso")


class ReturnUpdateSchema(BaseModel):
    """Schema per l'aggiornamento di un reso"""
    includes_shipping: Optional[bool] = Field(None, description="Se includere le spese di spedizione")
    note: Optional[str] = Field(None, description="Note aggiuntive per il reso")
    status: Optional[str] = Field(None, description="Stato del reso (pending, processed, cancelled)")


class ReturnDetailUpdateSchema(BaseModel):
    """Schema per l'aggiornamento di un dettaglio reso"""
    quantity: Optional[int] = Field(None, gt=0, description="Nuova quantità")
    unit_price: Optional[float] = Field(None, gt=0, description="Nuovo prezzo unitario")
    id_tax: Optional[int] = Field(None, gt=0, description="Nuovo ID della tassa applicata")



class ReturnResponseSchema(BaseModel):
    """Schema di risposta per un reso"""
    id_fiscal_document: int
    id_order: int
    document_number: Optional[str]
    customer: Optional[CustomerResponseSchema] = None
    address_delivery: Optional[AddressResponseSchema] = None
    address_invoice: Optional[AddressResponseSchema] = None
    payment: Optional[PaymentResponseSchema] = None
    shipping: Optional[ShippingResponseSchema] = None
    date_add: Optional[datetime]
    filename: Optional[str]
    xml_content: Optional[str]
    status: Optional[str]
    upload_result: Optional[str]
    date_upd: Optional[datetime]
    document_type: str
    tipo_documento_fe: Optional[str]
    id_fiscal_document_ref: Optional[int]
    internal_number: Optional[str]
    credit_note_reason: Optional[str]
    is_partial: bool
    total_price_with_tax: Optional[float] = None
    includes_shipping: bool
    details: List["ReturnDetailResponseSchema"] = Field(default_factory=list, description="Righe/dettagli del documento fiscale")

    class Config:
        from_attributes = True


class ReturnDetailResponseSchema(BaseModel):
    """Schema di risposta per un dettaglio reso (stessa struttura di OrderDetailResponseSchema + id_fiscal_document_detail/id_fiscal_document)."""
    # Campi in comune con OrderDetailResponseSchema
    id_order_detail: int
    id_order: Optional[int] = None
    id_order_document: Optional[int] = None
    id_origin: Optional[int] = None
    id_tax: Optional[int] = None
    id_product: Optional[int] = None
    product_name: Optional[str] = None
    product_reference: Optional[str] = None
    product_qty: int = 0
    unit_price_net: Optional[float] = None
    unit_price_with_tax: float = 0.0
    total_price_net: float = 0.0
    total_price_with_tax: float = 0.0
    product_weight: Optional[float] = None
    reduction_percent: Optional[float] = None
    reduction_amount: Optional[float] = None
    rda: Optional[str] = None
    rda_quantity: Optional[int] = None
    note: Optional[str] = None
    img_url: Optional[str] = None
    # Campi specifici del reso
    id_fiscal_document_detail: Optional[int] = None
    id_fiscal_document: Optional[int] = None

    class Config:
        from_attributes = True


class ReturnDocumentResponseSchema(BaseModel):
    """Schema di risposta completo per un reso (documento + dettagli righe)"""
    id_fiscal_document: int
    id_order: int
    document_number: Optional[str] = None
    internal_number: Optional[str] = None
    tipo_documento_fe: Optional[str] = None
    xml_content: Optional[str] = None
    is_electronic: bool = False
    includes_shipping: bool = False

    products_total_price_net: Optional[float] = None
    products_total_price_with_tax: Optional[float] = None
    total_price_with_tax: Optional[float] = None
    total_price_net: Optional[float] = None
    status: str
    upload_result: Optional[str] = None
    date_add: Optional[datetime] = None
    date_upd: Optional[datetime] = None
    details: List[ReturnDetailResponseSchema] = Field(
        default_factory=list,
        serialization_alias="fiscal_document_detail",
        description="Lista dei dettagli (righe) del reso"
    )

    class Config:
        from_attributes = True


class ReturnWithDetailsResponseSchema(ReturnResponseSchema):
    """Schema di risposta per un reso con i suoi dettagli"""
    details: List[ReturnDetailResponseSchema] = []


class AllReturnsResponseSchema(BaseModel):
    """Schema di risposta per la lista di tutti i resi"""
    returns: List[ReturnResponseSchema]
    total: int
    page: int
    limit: int
