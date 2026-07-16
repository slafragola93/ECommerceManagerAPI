from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, Field, field_validator

from src.models.order import ViesStatus
from src.services.ricevute.date_utils import parse_emission_input


class RicevutaStatoSchema(str, Enum):
    EMESSA = "emessa"
    ANNULLATA = "annullata"


class RicevutaExportFormatSchema(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"


class RicevutaCreateSchema(BaseModel):
    id_order: int = Field(..., gt=0, description="Ordine collegato")
    data_emissione: Optional[Union[date, datetime]] = Field(
        None,
        description=(
            "Data e ora emissione (Europe/Rome, ISO 8601); "
            "default: adesso. Accetta anche solo la data (ora corrente)."
        ),
    )

    @field_validator("data_emissione", mode="before")
    @classmethod
    def _parse_data_emissione(cls, value):
        return parse_emission_input(value)


class RicevutaUpdateSchema(BaseModel):
    data_emissione: Union[date, datetime] = Field(
        ..., description="Nuova data e ora emissione (Europe/Rome)"
    )

    @field_validator("data_emissione", mode="before")
    @classmethod
    def _parse_data_emissione(cls, value):
        parsed = parse_emission_input(value)
        if parsed is None:
            raise ValueError("data_emissione è obbligatoria")
        return parsed


class RicevutaOrderDetailEmbedSchema(BaseModel):
    """Riga prodotto live da `order_details` (subset UI/PDF)."""

    id_order_detail: int
    id_product: Optional[int] = None
    product_name: Optional[str] = None
    product_reference: Optional[str] = None
    product_qty: int = Field(..., ge=0)
    product_weight: Optional[float] = Field(
        None,
        description="Peso unitario kg (order_detail o fallback products.weight)",
    )
    id_tax: Optional[int] = None
    unit_price_net: Optional[float] = None
    unit_price_with_tax: Optional[float] = None
    total_price_net: Optional[float] = None
    total_price_with_tax: Optional[float] = None
    reduction_percent: Optional[float] = None
    reduction_amount: Optional[float] = None
    is_shipping: bool = Field(
        False,
        description="True per la riga spedizione sintetica (id_order_detail=0)",
    )


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


class RicevutaPaymentEmbedSchema(BaseModel):
    """Metodo pagamento ordine (subset GET order)."""

    id_payment: int
    name: str


class RicevutaCarrierApiEmbedSchema(BaseModel):
    id_carrier_api: int
    name: Optional[str] = None


class RicevutaTaxEmbedSchema(BaseModel):
    id_tax: int
    code: Optional[str] = None
    percentage: Optional[float] = None
    name: Optional[str] = None


class RicevutaShippingEmbedSchema(BaseModel):
    """Contesto logistico spedizione — importi in `shipping_total_price_*` root."""

    id_shipping: int
    carrier_api: Optional[RicevutaCarrierApiEmbedSchema] = None
    tax: Optional[RicevutaTaxEmbedSchema] = None
    weight: Optional[float] = None
    shipping_message: Optional[str] = None


class RicevutaListItemSchema(BaseModel):
    id_ricevuta: int
    numero: int
    anno: int
    data_incasso: date
    data_emissione: datetime
    stato: RicevutaStatoSchema
    pdf_path: Optional[str] = None
    pdf_generated_at: Optional[datetime] = None
    id_order: int
    order_reference: Optional[str] = None
    order_total_with_tax: Optional[float] = None
    customer: Optional[RicevutaCustomerEmbedSchema] = None


class RicevutaResponseSchema(BaseModel):
    """
    Dettaglio ricevuta — contratto v3.

    - `id_order` / totali / pagamento / spedizione in root (no oggetto `order` annidato).
    - `id_customer` solo in `customer` (non duplicato in root).
    - Importi spedizione solo in `shipping_total_price_*` (non in `shipping`).
    - Data incasso: solo `data_incasso` (non duplicare con `payment_date` ordine).
    - Indirizzi in `address_delivery` e `address_invoice` (nullable).
    - Se l'ordine cambia: riemissione documento (DELETE + POST), non aggiornamento automatico.
    - `pdf_hash` omesso (uso interno BE).
    """

    id_ricevuta: int
    numero: int
    anno: int
    data_incasso: date
    data_emissione: datetime
    stato: RicevutaStatoSchema
    pdf_path: Optional[str] = None
    pdf_generated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    annullata_at: Optional[datetime] = None
    annullata_da_user_id: Optional[int] = None
    is_modifiable: bool = Field(
        description=(
            "False se l'ordine è in Spedizione Confermata (id_order_state=4). "
            "Indicatore FE per eventuali warning: POST/PUT/DELETE non sono bloccati dal BE."
        )
    )

    id_order: int
    order_reference: Optional[str] = None
    id_order_state: Optional[int] = None
    total_weight: Optional[float] = Field(
        None,
        description=(
            "Peso totale ordine (kg): `orders.total_weight` se > 0, "
            "altrimenti somma live `product_weight * product_qty` delle righe ordine"
        ),
    )

    vies_status: Optional[ViesStatus] = None
    is_payed: bool = False
    payment_due_date: Optional[date] = None

    payment: Optional[RicevutaPaymentEmbedSchema] = None
    shipping: Optional[RicevutaShippingEmbedSchema] = None

    total_price_with_tax: float = 0.0
    total_price_net: Optional[float] = None
    products_total_price_with_tax: Optional[float] = None
    products_total_price_net: Optional[float] = None
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
        description="Righe prodotto + eventuale riga spedizione (`is_shipping=true`)",
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
