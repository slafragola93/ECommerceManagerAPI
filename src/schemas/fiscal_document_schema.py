from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


# ==================== SCHEMAS PER DETTAGLI ====================

class FiscalDocumentDetailSchema(BaseModel):
    """Schema per dettaglio nota di credito parziale"""
    id_order_detail: int = Field(..., gt=0, description="ID dell'order detail da stornare")
    quantity: float = Field(..., gt=0, description="Quantità da stornare")
    id_tax: Optional[int] = Field(None, gt=0, description="ID della tassa applicata")
    
    class Config:
        from_attributes = True


class FiscalDocumentDetailResponseSchema(BaseModel):
    """Schema risposta per dettaglio"""
    id_fiscal_document_detail: int
    id_fiscal_document: int
    id_order_detail: int
    quantity: float
    unit_price: float
    total_amount: float
    id_tax: Optional[int] = None
    
    class Config:
        from_attributes = True


class FiscalDocumentDetailWithProductSchema(BaseModel):
    """Schema risposta dettaglio arricchito con info prodotto"""
    id_fiscal_document_detail: int
    id_fiscal_document: int
    id_order_detail: int
    quantity: float
    unit_price: float
    total_amount: float
    id_tax: Optional[int] = None
    
    # Info prodotto
    product_name: Optional[str] = None
    product_reference: Optional[str] = None
    
    class Config:
        from_attributes = True


# ==================== SCHEMAS PER FATTURE ====================

class InvoiceCreateSchema(BaseModel):
    """Schema per creazione fattura"""
    id_order: int = Field(..., gt=0, description="ID dell'ordine")
    is_electronic: bool = Field(True, description="Se True, genera fattura elettronica (solo per indirizzi IT)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id_order": 12345,
                "is_electronic": True
            }
        }


class InvoiceResponseSchema(BaseModel):
    """Schema risposta fattura"""
    id_fiscal_document: int
    document_type: str
    tipo_documento_fe: Optional[str]
    id_order: int
    document_number: Optional[str]
    internal_number: Optional[str]
    filename: Optional[str]
    status: str
    is_electronic: bool
    includes_shipping: bool
    total_amount: Optional[float]
    date_add: Optional[datetime] = None
    date_upd: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ==================== SCHEMAS PER NOTE DI CREDITO ====================

class CreditNoteCreateSchema(BaseModel):
    """Schema per creazione nota di credito"""
    id_invoice: int = Field(..., gt=0, description="ID della fattura di riferimento")
    reason: str = Field(..., min_length=1, max_length=500, description="Motivo della nota di credito")
    is_partial: bool = Field(False, description="Se True, nota di credito parziale")
    is_electronic: bool = Field(True, description="Se True, genera XML elettronico")
    include_shipping: bool = Field(True, description="Se True, include spese di spedizione (solo per note totali o se non già stornate)")
    items: Optional[List[FiscalDocumentDetailSchema]] = Field(
        None, 
        description="Articoli da stornare (obbligatorio se is_partial=True)"
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "summary": "Nota di credito totale (con spedizione)",
                    "value": {
                        "id_invoice": 123,
                        "reason": "Reso merce",
                        "is_partial": False,
                        "is_electronic": True,
                        "include_shipping": True
                    }
                },
                {
                    "summary": "Nota di credito totale (senza spedizione)",
                    "value": {
                        "id_invoice": 123,
                        "reason": "Reso merce - spedizione già stornata",
                        "is_partial": False,
                        "is_electronic": True,
                        "include_shipping": False
                    }
                },
                {
                    "summary": "Nota di credito parziale",
                    "value": {
                        "id_invoice": 123,
                        "reason": "Reso parziale - articolo difettoso",
                        "is_partial": True,
                        "is_electronic": True,
                        "include_shipping": False,
                        "items": [
                            {
                                "id_order_detail": 456,
                                "quantity": 2.0
                            }
                        ]
                    }
                }
            ]
        }


class CreditNoteResponseSchema(BaseModel):
    """Schema risposta nota di credito"""
    id_fiscal_document: int
    document_type: str
    tipo_documento_fe: Optional[str]
    id_order: int
    id_fiscal_document_ref: Optional[int]
    document_number: Optional[str]
    internal_number: Optional[str]
    filename: Optional[str]
    status: str
    is_electronic: bool
    credit_note_reason: Optional[str]
    is_partial: bool
    includes_shipping: bool
    total_amount: Optional[float]
    date_add: Optional[datetime] = None
    date_upd: Optional[datetime] = None
    details: List[FiscalDocumentDetailResponseSchema] = []
    
    class Config:
        from_attributes = True


# ==================== SCHEMAS UNIFICATI ====================

class FiscalDocumentResponseSchema(BaseModel):
    """Schema risposta generico per qualsiasi documento fiscale"""
    id_fiscal_document: int
    document_type: str  # 'invoice' o 'credit_note'
    tipo_documento_fe: Optional[str]
    id_order: int
    id_fiscal_document_ref: Optional[int]
    document_number: Optional[str]
    internal_number: Optional[str]
    filename: Optional[str]
    xml_content: Optional[str]
    status: str
    is_electronic: bool
    upload_result: Optional[str]
    credit_note_reason: Optional[str]
    is_partial: bool
    total_amount: Optional[float]
    date_add: Optional[datetime] = None
    date_upd: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class FiscalDocumentListResponseSchema(BaseModel):
    """Schema risposta lista documenti fiscali"""
    documents: List[FiscalDocumentResponseSchema]
    total: int
    page: int
    limit: int


# ==================== SCHEMAS PER UPDATE ====================

class FiscalDocumentUpdateStatusSchema(BaseModel):
    """Schema per aggiornamento status"""
    status: str = Field(..., description="Nuovo status (pending, generated, uploaded, sent, error)")
    upload_result: Optional[str] = Field(None, description="Risultato upload (JSON)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "sent",
                "upload_result": '{"sdi_id": "12345", "timestamp": "2024-01-01T10:00:00"}'
            }
        }


class FiscalDocumentUpdateXMLSchema(BaseModel):
    """Schema per aggiornamento XML"""
    filename: str = Field(..., description="Nome file XML")
    xml_content: str = Field(..., description="Contenuto XML")
    
    class Config:
        json_schema_extra = {
            "example": {
                "filename": "IT01234567890_00001.xml",
                "xml_content": "<?xml version='1.0' encoding='UTF-8'?>..."
            }
        }
