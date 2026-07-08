from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class RicevutaStatoSchema(str, Enum):
    EMESSA = "emessa"
    ANNULLATA = "annullata"


class RicevutaExportFormatSchema(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"


class RicevutaCreateSchema(BaseModel):
    id_order: int = Field(..., gt=0, description="Ordine collegato")
    data_emissione: Optional[date] = Field(
        None, description="Data emissione; default: oggi (Europe/Rome)"
    )


class RicevutaUpdateSchema(BaseModel):
    data_emissione: date = Field(..., description="Nuova data emissione")


class RicevutaOrderDetailEmbedSchema(BaseModel):
    """Riga prodotto live da `order_details` (subset UI/PDF)."""

    id_order_detail: int
    id_product: Optional[int] = None
    product_name: Optional[str] = None
    product_reference: Optional[str] = None
    product_qty: int = Field(..., ge=0)
    id_tax: Optional[int] = None
    unit_price_net: Optional[float] = None
    unit_price_with_tax: Optional[float] = None
    total_price_net: Optional[float] = None
    total_price_with_tax: Optional[float] = None
    reduction_percent: Optional[float] = None
    reduction_amount: Optional[float] = None


class RicevutaCustomerEmbedSchema(BaseModel):
    """Cliente essenziale — unica occorrenza in dettaglio/lista."""

    id_customer: int
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    email: Optional[str] = None


class RicevutaCountryEmbedSchema(BaseModel):
    iso_code: Optional[str] = None
    name: Optional[str] = None


class RicevutaAddressEmbedSchema(BaseModel):
    """Indirizzo per stampa/UI — senza customer annidato (già in `customer`)."""

    id_address: int
    company: Optional[str] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    postcode: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None
    vat: Optional[str] = None
    country: Optional[RicevutaCountryEmbedSchema] = None


class RicevutaOrderEmbedSchema(BaseModel):
    """Ordine live — PK e totali; `is_modifiable` solo a livello ricevuta."""

    id_order: int
    reference: Optional[str] = None
    id_order_state: int
    is_payed: bool
    payment_date: Optional[date] = None
    total_price_with_tax: float
    total_price_net: Optional[float] = None
    products_total_price_with_tax: Optional[float] = None
    products_total_price_net: Optional[float] = None
    total_discounts: Optional[float] = None
    general_note: Optional[str] = None


class RicevutaListItemSchema(BaseModel):
    id_ricevuta: int
    numero: int
    anno: int
    data_incasso: date
    data_emissione: date
    stato: RicevutaStatoSchema
    pdf_path: Optional[str] = None
    pdf_generated_at: Optional[datetime] = None
    id_order: int
    order_reference: Optional[str] = None
    order_total_with_tax: Optional[float] = None
    customer: Optional[RicevutaCustomerEmbedSchema] = None


class RicevutaResponseSchema(BaseModel):
    """
    Dettaglio ricevuta — contratto snello.

    - Nessun `id_order`/`id_customer` duplicati in root (solo in `order` / `customer`).
    - Indirizzo unico in `address` se consegna = fatturazione; altrimenti delivery/invoice.
    - `pdf_hash` omesso (uso interno BE).
    """

    id_ricevuta: int
    numero: int
    anno: int
    data_incasso: date
    data_emissione: date
    stato: RicevutaStatoSchema
    pdf_path: Optional[str] = None
    pdf_generated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    annullata_at: Optional[datetime] = None
    annullata_da_user_id: Optional[int] = None
    is_modifiable: bool = Field(
        description="False se l'ordine collegato è in Spedizione Confermata"
    )
    customer: Optional[RicevutaCustomerEmbedSchema] = None
    order: Optional[RicevutaOrderEmbedSchema] = None
    address: Optional[RicevutaAddressEmbedSchema] = Field(
        None,
        description="Presente se indirizzo consegna e fatturazione coincidono",
    )
    address_delivery: Optional[RicevutaAddressEmbedSchema] = Field(
        None,
        description="Solo se diverso da fatturazione",
    )
    address_invoice: Optional[RicevutaAddressEmbedSchema] = Field(
        None,
        description="Solo se diverso da consegna",
    )
    order_details: List[RicevutaOrderDetailEmbedSchema] = Field(
        default_factory=list,
        description="Righe prodotto live dall'ordine collegato",
    )


class RicevutaListResponseSchema(BaseModel):
    ricevute: List[RicevutaListItemSchema]
    total: int
    page: int
    limit: int


class RicevutaFiltersSchema(BaseModel):
    id_order: Optional[int] = Field(None, gt=0)
    id_customer: Optional[int] = Field(None, gt=0)
    stato: Optional[RicevutaStatoSchema] = None
    data_emissione_from: Optional[date] = None
    data_emissione_to: Optional[date] = None
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=500)

    @field_validator("data_emissione_to")
    @classmethod
    def validate_date_range(cls, end: Optional[date], info):
        start = info.data.get("data_emissione_from")
        if start and end and end < start:
            raise ValueError("data_emissione_to deve essere >= data_emissione_from")
        return end
