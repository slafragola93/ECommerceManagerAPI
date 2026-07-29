from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PurchaseInvoiceDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    numero_linea: int
    descrizione: Optional[str] = None
    codice_articolo: Optional[str] = None
    quantita: Optional[Decimal] = None
    unita_misura: Optional[str] = None
    prezzo_unitario: Optional[Decimal] = None
    prezzo_totale: Optional[Decimal] = None
    aliquota_iva: Optional[Decimal] = None
    natura: Optional[str] = None


class PurchaseInvoiceListItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identificativo_sdi: str
    nome_file: str
    tipo_documento: Optional[str] = None
    numero_documento: Optional[str] = None
    data_documento: Optional[date] = None
    fornitore_denominazione: Optional[str] = None
    fornitore_piva: Optional[str] = None
    importo_totale: Optional[Decimal] = None
    fattura_collegata_numero: Optional[str] = None
    fattura_collegata_data: Optional[date] = None
    is_paid: bool = False
    id_payment: Optional[int] = None
    payment_name: Optional[str] = None
    paid_at: Optional[datetime] = None
    direzione: Optional[str] = None
    tipo: Optional[str] = None
    created_at: Optional[datetime] = None


class PurchaseInvoiceDetailResponseSchema(PurchaseInvoiceListItemSchema):
    note: Optional[str] = None
    blob_uri: Optional[str] = None
    file_path: Optional[str] = None
    details: List[PurchaseInvoiceDetailSchema] = Field(default_factory=list)


class AllPurchaseInvoicesResponseSchema(BaseModel):
    items: List[PurchaseInvoiceListItemSchema]
    total: int
    page: int
    limit: int


class PurchaseInvoicePaymentUpdateSchema(BaseModel):
    is_paid: bool = Field(..., description="True = pagato, False = da pagare")
    id_payment: Optional[int] = Field(
        None, gt=0, description="Obbligatorio se is_paid=true"
    )


class PurchaseInvoiceSyncResultSchema(BaseModel):
    status: str
    entries_found: int = 0
    entries_processed: int = 0
    entries_downloaded: int = 0
    entries_saved: int = 0
    entries_skipped: int = 0
    errors: List[str] = Field(default_factory=list)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
