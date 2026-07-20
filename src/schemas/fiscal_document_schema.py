from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, validator
from datetime import date, datetime

from src.models.order import ViesStatus
from src.schemas.ricevuta_schema import (
    RicevutaAddressEmbedSchema,
    RicevutaCustomerEmbedSchema,
    RicevutaOrderDetailEmbedSchema,
    RicevutaPaymentEmbedSchema,
    RicevutaShippingEmbedSchema,
)


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
    product_qty: float
    unit_price_net: Optional[float] = None
    unit_price_with_tax: float
    total_price_net: float
    total_price_with_tax: float
    id_tax: Optional[int] = None
    
    @validator('product_qty', 'unit_price_net', 'unit_price_with_tax', 'total_price_net',
               'total_price_with_tax', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)
    
    class Config:
        from_attributes = True
    
    # Backward compatibility: unit_price come alias per unit_price_net
    @property
    def unit_price(self):
        return self.unit_price_net
    
    @unit_price.setter
    def unit_price(self, value):
        self.unit_price_net = value


class FiscalDocumentDetailWithProductSchema(BaseModel):
    """Schema risposta dettaglio arricchito con info prodotto"""
    id_fiscal_document_detail: int
    id_fiscal_document: int
    id_order_detail: int
    product_qty: float
    unit_price_net: Optional[float] = None
    unit_price_with_tax: float
    total_price_net: float
    total_price_with_tax: float
    id_tax: Optional[int] = None
    
    # Info prodotto
    product_name: Optional[str] = None
    product_reference: Optional[str] = None
    
    class Config:
        from_attributes = True
    
    # Backward compatibility: unit_price come alias per unit_price_net
    @property
    def unit_price(self):
        return self.unit_price_net
    
    @unit_price.setter
    def unit_price(self, value):
        self.unit_price_net = value


# ==================== SCHEMAS PER FATTURE ====================

class InvoiceCreateSchema(BaseModel):
    """Schema per creazione fattura"""
    id_order: int = Field(..., gt=0, description="ID dell'ordine")
    is_electronic: bool = Field(True, description="Se True, genera fattura elettronica FatturaPA (cliente IT o UE/VIES)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id_order": 12345,
                "is_electronic": True
            }
        }


class InvoiceResponseSchema(BaseModel):
    """Schema risposta fattura (dettaglio GET/POST): campi documento + contesto ordine come ricevuta v3."""

    id_fiscal_document: int
    document_type: str
    tipo_documento_fe: Optional[str] = None
    id_order: int
    document_number: Optional[str] = None
    internal_number: Optional[str] = None
    filename: Optional[str] = None
    xml_content: Optional[str] = None
    status: str
    is_electronic: bool
    upload_result: Optional[str] = None
    includes_shipping: bool
    total_price_with_tax: Optional[float] = None
    total_price_net: Optional[float] = None
    products_total_price_net: Optional[float] = None
    products_total_price_with_tax: Optional[float] = None
    date_add: Optional[datetime] = None
    date_upd: Optional[datetime] = None

    order_reference: Optional[str] = None
    id_order_state: Optional[int] = None
    total_weight: Optional[float] = Field(
        None,
        description="Peso totale ordine (kg), stessa risoluzione della ricevuta v3",
    )
    vies_status: Optional[ViesStatus] = None
    is_payed: bool = False
    payment_due_date: Optional[date] = None

    payment: Optional[RicevutaPaymentEmbedSchema] = None
    shipping: Optional[RicevutaShippingEmbedSchema] = None
    shipping_total_price_with_tax: Optional[float] = None
    shipping_total_price_net: Optional[float] = None
    total_discounts: Optional[float] = None

    customer: Optional[RicevutaCustomerEmbedSchema] = None
    address_delivery: Optional[RicevutaAddressEmbedSchema] = Field(
        None,
        description="Indirizzo consegna da ordine collegato",
    )
    address_invoice: Optional[RicevutaAddressEmbedSchema] = Field(
        None,
        description="Indirizzo fatturazione da ordine collegato",
    )
    order_details: List[RicevutaOrderDetailEmbedSchema] = Field(
        default_factory=list,
        description="Righe snapshot documento fiscale + eventuale riga spedizione",
    )

    @validator(
        "total_price_with_tax",
        "total_price_net",
        "products_total_price_net",
        "products_total_price_with_tax",
        "total_weight",
        "shipping_total_price_with_tax",
        "shipping_total_price_net",
        "total_discounts",
        pre=True,
        allow_reuse=True,
    )
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)


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
    total_price_with_tax: Optional[float] = None
    total_price_net: Optional[float] = None
    products_total_price_net: Optional[float] = None
    products_total_price_with_tax: Optional[float] = None
    date_add: Optional[datetime] = None
    date_upd: Optional[datetime] = None
    details: List[FiscalDocumentDetailResponseSchema] = []

    @validator('total_price_with_tax', 'total_price_net', 'products_total_price_net', 'products_total_price_with_tax', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)

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
    total_price_with_tax: Optional[float] = None
    total_price_net: Optional[float] = None
    products_total_price_net: Optional[float] = None
    products_total_price_with_tax: Optional[float] = None
    date_add: Optional[datetime] = None
    date_upd: Optional[datetime] = None

    @validator('total_price_with_tax', 'total_price_net', 'products_total_price_net', 'products_total_price_with_tax', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)
    
    class Config:
        from_attributes = True


class FiscalDocumentListResponseSchema(BaseModel):
    """Schema risposta lista documenti fiscali"""
    documents: List[FiscalDocumentResponseSchema]
    total: int
    page: int
    limit: int


# ==================== EXPORT LISTA FATTURE ====================


class InvoiceExportFormatSchema(str, Enum):
    XLSX = "xlsx"
    XML = "xml"


class InvoiceExportFiltersSchema(BaseModel):
    """Filtri export massivo fatture."""

    is_electronic: Optional[bool] = None
    status: Optional[str] = None
    id_order: Optional[int] = Field(None, gt=0)
    id_customer: Optional[int] = Field(None, gt=0)
    delivery_country_iso: Optional[str] = Field(
        None,
        min_length=2,
        max_length=5,
        description="ISO paese consegna (determina aliquota IVA)",
    )
    date_add_from: Optional[date] = None
    date_add_to: Optional[date] = None
    page: int = Field(1, ge=1)
    limit: int = Field(100, ge=1, le=5000)

    def for_xml_export(self, max_limit: int = 5000) -> "InvoiceExportFiltersSchema":
        """Export XML: date, paese consegna + solo fatture elettroniche (FatturaPA)."""
        return self.model_copy(
            update={
                "is_electronic": True,
                "status": None,
                "id_order": None,
                "id_customer": None,
                "page": 1,
                "limit": max_limit,
            }
        )

    @field_validator("delivery_country_iso")
    @classmethod
    def normalize_country_iso(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip().upper()

    @field_validator("date_add_to")
    @classmethod
    def validate_date_range(cls, end: Optional[date], info):
        start = info.data.get("date_add_from")
        if start and end and end < start:
            raise ValueError("date_add_to deve essere >= date_add_from")
        return end


class InvoiceListExportItemSchema(BaseModel):
    """Riga lista fatture per export Excel."""

    id_fiscal_document: int
    document_number: Optional[str] = None
    internal_number: Optional[str] = None
    tipo_documento_fe: Optional[str] = None
    status: str
    is_electronic: bool
    id_order: int
    order_reference: Optional[str] = None
    customer_firstname: Optional[str] = None
    customer_lastname: Optional[str] = None
    customer_email: Optional[str] = None
    delivery_country_iso: Optional[str] = None
    delivery_city: Optional[str] = None
    date_add: Optional[datetime] = None
    total_price_net: Optional[float] = None
    total_price_with_tax: Optional[float] = None
    products_total_price_net: Optional[float] = None
    products_total_price_with_tax: Optional[float] = None

    @validator(
        "total_price_net",
        "total_price_with_tax",
        "products_total_price_net",
        "products_total_price_with_tax",
        pre=True,
        allow_reuse=True,
    )
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)


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
