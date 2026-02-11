"""
Schemi per la gestione dei resi
"""
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime


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
    
    class Config:
        from_attributes = True


class ReturnDetailResponseSchema(BaseModel):
    """Schema di risposta per un dettaglio reso"""
    id_fiscal_document_detail: int
    id_fiscal_document: int
    id_order_detail: int
    product_qty: float
    unit_price: float
    total_price_with_tax: float

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
