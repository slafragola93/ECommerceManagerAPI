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


class CreditNoteEligibleLineSchema(FiscalDocumentDetailWithProductSchema):
    """Riga fattura eleggibile per nota di credito parziale."""

    refunded_qty: float = Field(0, ge=0, description="Quantità già stornata in NC precedenti")
    remaining_qty: float = Field(..., ge=0, description="Quantità ancora stornabile")
    is_fully_refunded: bool = Field(
        False, description="True se remaining_qty <= 0"
    )

    @validator(
        "product_qty",
        "refunded_qty",
        "remaining_qty",
        "unit_price_net",
        "unit_price_with_tax",
        "total_price_net",
        "total_price_with_tax",
        pre=True,
        allow_reuse=True,
    )
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)


class CreditNoteEligibleShippingSchema(BaseModel):
    """Importi spedizione fatturati (per toggle include_shipping in NC)."""

    unit_price_net: Optional[float] = None
    unit_price_with_tax: Optional[float] = None
    id_tax: Optional[int] = None

    @validator("unit_price_net", "unit_price_with_tax", pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)


class CreditNoteEligibleLinesResponseSchema(BaseModel):
    """Payload minimale per modale NC parziale."""

    id_fiscal_document: int = Field(..., description="ID fattura di riferimento")
    id_order: int
    includes_shipping: bool = Field(
        ..., description="La fattura include spese di spedizione"
    )
    shipping_already_refunded: bool = Field(
        ..., description="True se una NC precedente ha includes_shipping=true"
    )
    shipping_eligible: bool = Field(
        ...,
        description="True se la spedizione può ancora essere stornata (includes_shipping e non già stornata, con importo > 0)",
    )
    has_total_credit_note: bool = Field(
        ..., description="True se esiste già una NC totale sulla fattura"
    )
    can_create_credit_note: bool = Field(
        ..., description="False se has_total_credit_note (nessuna altra NC ammessa)"
    )
    shipping: Optional[CreditNoteEligibleShippingSchema] = None
    details: List[CreditNoteEligibleLineSchema] = Field(default_factory=list)


# ==================== SCHEMAS PER FATTURE ====================

class InvoiceCreateSchema(BaseModel):
    """Schema per creazione fattura (sempre elettronica FatturaPA, is_electronic=True)."""
    id_order: int = Field(..., gt=0, description="ID dell'ordine")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id_order": 12345,
            }
        }


class InvoiceResponseSchema(BaseModel):
    """Schema risposta documento fiscale attivo (fattura TD01 / nota di credito TD04).

    Contratto v3 arricchito condiviso: differenziare tramite `document_type`.
    Campi NC-specifici (`id_fiscal_document_ref`, `credit_note_reason`, `is_partial`)
    sono valorizzati solo se `document_type=credit_note`.
    """

    id_fiscal_document: int
    document_type: str
    tipo_documento_fe: Optional[str] = None
    id_order: int
    id_fiscal_document_ref: Optional[int] = Field(
        None, description="ID fattura di riferimento (solo credit_note)"
    )
    document_number: Optional[str] = None
    internal_number: Optional[str] = None
    filename: Optional[str] = None
    xml_content: Optional[str] = None
    status: str
    is_electronic: bool
    upload_result: Optional[str] = None
    credit_note_reason: Optional[str] = Field(
        None, description="Motivo nota di credito (solo credit_note)"
    )
    is_partial: Optional[bool] = Field(
        None, description="Nota di credito parziale (solo credit_note)"
    )
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
    """Schema per creazione nota di credito (sempre elettronica FatturaPA TD04, is_electronic=True)."""
    id_invoice: int = Field(..., gt=0, description="ID della fattura di riferimento")
    reason: str = Field(..., min_length=1, max_length=500, description="Motivo della nota di credito")
    is_partial: bool = Field(False, description="Se True, nota di credito parziale")
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
                        "include_shipping": True
                    }
                },
                {
                    "summary": "Nota di credito totale (senza spedizione)",
                    "value": {
                        "id_invoice": 123,
                        "reason": "Reso merce - spedizione già stornata",
                        "is_partial": False,
                        "include_shipping": False
                    }
                },
                {
                    "summary": "Nota di credito parziale",
                    "value": {
                        "id_invoice": 123,
                        "reason": "Reso parziale - articolo difettoso",
                        "is_partial": True,
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


class CreditNoteResponseSchema(InvoiceResponseSchema):
    """Alias di InvoiceResponseSchema per nota di credito (stesso contratto v3)."""

    pass


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


class FiscalDocumentListFiltersSchema(BaseModel):
    """Filtri lista paginata documenti fiscali (GET /fiscal_documents/)."""

    document_type: Optional[str] = None
    is_electronic: Optional[bool] = None
    status: Optional[str] = None
    delivery_country_iso: Optional[str] = Field(
        None,
        min_length=2,
        max_length=5,
        description="ISO paese consegna ordine (stessa logica export/corrispettivi)",
    )
    date_add_from: Optional[date] = None
    date_add_to: Optional[date] = None
    page: int = Field(1, ge=1)
    limit: int = Field(100, ge=1, le=1000)

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


# ==================== EXPORT LISTA FATTURE ====================


class InvoiceExportFormatSchema(str, Enum):
    XLSX = "xlsx"
    XML = "xml"


class InvoiceExportFiltersSchema(BaseModel):
    """Filtri export massivo documenti fiscali elettronici (fatture / note di credito)."""

    document_type: str = Field(
        "invoice",
        description="Tipo documento: invoice o credit_note",
    )
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
        """Export XML: date, paese consegna + solo documenti elettronici (FatturaPA)."""
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

    @field_validator("document_type")
    @classmethod
    def normalize_document_type(cls, value: str) -> str:
        normalized = (value or "invoice").strip().lower()
        if normalized not in ("invoice", "credit_note"):
            raise ValueError("document_type deve essere invoice o credit_note")
        return normalized

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
    """Riga lista documenti fiscali per export Excel."""

    id_fiscal_document: int
    document_type: str
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
