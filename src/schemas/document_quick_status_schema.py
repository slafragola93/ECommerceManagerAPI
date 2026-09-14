"""Campi stati rapidi condivisi (lista + dettaglio documenti)."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

FatturapaStatusLiteral = Optional[Literal["uploaded", "sent", "error"]]
MailStatusLiteral = Optional[Literal["sent", "pending", "error"]]


class LifecycleChannelSchema(BaseModel):
    status: Optional[str] = None
    error_message: Optional[str] = None


class LifecycleFatturapaSchema(LifecycleChannelSchema):
    identificativo_sdi: Optional[str] = None


class FiscalDocumentLifecycleSchema(BaseModel):
    """Stati raggruppati per sottosistema. I campi flat restano per compatibilità FE."""

    status: str = Field(..., description="Workflow persistito (stesso valore di `status`)")
    fatturapa: LifecycleFatturapaSchema
    sdi: LifecycleChannelSchema
    mail: LifecycleChannelSchema


class DocumentQuickStatusSchema(BaseModel):
    """Contratto FE colonna Stato rapido — esito intermediario FatturaPA."""

    mail_status: MailStatusLiteral = Field(
        None,
        description="Deprecated: preferire lifecycle.mail.status",
    )
    mail_error_message: Optional[str] = Field(
        None, description="Deprecated: preferire lifecycle.mail.error_message"
    )
    fatturapa_status: FatturapaStatusLiteral = Field(
        None,
        description=(
            "Deprecated: preferire lifecycle.fatturapa.status. "
            "Overlay calcolato: uploaded|sent|error|null. Non è copia di `status`."
        ),
    )
    fatturapa_error_message: Optional[str] = Field(
        None, description="Deprecated: preferire lifecycle.fatturapa.error_message"
    )
    identificativo_sdi: Optional[str] = Field(
        None, description="Deprecated: preferire lifecycle.fatturapa.identificativo_sdi"
    )
    lifecycle: Optional[FiscalDocumentLifecycleSchema] = Field(
        None,
        description="Stati per sottosistema (workflow + FatturaPA + SDI + mail)",
    )
