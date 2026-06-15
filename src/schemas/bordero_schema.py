"""Schemi Pydantic per la feature Bordero (riepilogo spedizioni).

Espone solo `BorderoGenerateRequest` come contratto pubblico dell'endpoint
`POST /api/v1/bordero/generate`. `BorderoRow` e una struttura interna usata
per passare i dati gia normalizzati dal `BorderoService` al `BorderoPDFService`
senza dipendere dai modelli SQLAlchemy.
"""
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class BorderoGenerateRequest(BaseModel):
    """Body della richiesta `POST /api/v1/bordero/generate`."""

    carrier_id: int = Field(
        ...,
        gt=0,
        description="ID del corriere (carriers_api.id_carrier_api) selezionato dall'operatore.",
    )
    update_status: bool = Field(
        default=False,
        description=(
            "Se true, dopo la generazione del PDF tutti gli ordini inclusi vengono spostati "
            "a stato 'Spedizione Confermata' (id_order_state=4) in modalita best-effort."
        ),
    )
    date_from: Optional[date] = Field(
        default=None,
        description=(
            "Filtra ordini con `orders.date_add >= date_from` (estremo inclusivo). "
            "Stessa semantica di `GET /api/v1/orders/`. Il FE passa la finestra "
            "corrente della lista per evitare 'ordini fantasma' nel PDF."
        ),
    )
    date_to: Optional[date] = Field(
        default=None,
        description=(
            "Filtra ordini con `orders.date_add <= date_to` (estremo inclusivo). "
            "Stessa semantica di `GET /api/v1/orders/`."
        ),
    )


class BorderoZeroHintSchema(BaseModel):
    """Diagnostica quando il borderò non include spedizioni (count=0).

    Esposta al FE via header HTTP (`X-Bordero-Hint-*`) per messaggi mirati
    invece del generico "nessun ordine per questo corriere".
    """

    code: str = Field(
        ...,
        description=(
            "Codice machine-readable. Valori: `MISSING_TRACKING`, "
            "`INACTIVE_CARRIER`, `NO_ORDERS_FOR_CARRIER`, `GENERIC`."
        ),
    )
    message: str = Field(..., description="Messaggio operatore in italiano.")
    missing_tracking_count: int = Field(
        default=0,
        ge=0,
        description="Ordini Spediti con corriere corretto ma senza tracking.",
    )


class BorderoRow(BaseModel):
    """Una riga normalizzata del PDF bordero (1 riga = 1 spedizione)."""

    id_shipping: int
    id_order: int
    tracking: Optional[str] = None
    recipient: str = ""
    address: str = ""
    packages_count: int = 0
    weight: float = 0.0
    cash_on_delivery: float = 0.0
    articles: str = ""
    carrier_name: str = ""
