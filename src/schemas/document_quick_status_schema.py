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
    """Stati raggruppati per sottosistema (unica fonte in JSON lista/dettaglio fiscale)."""

    status: str = Field(..., description="Workflow persistito (stesso valore di `status`)")
    fatturapa: LifecycleFatturapaSchema
    sdi: LifecycleChannelSchema
    mail: LifecycleChannelSchema


_FLAT_LIFECYCLE_RESPONSE_KEYS = (
    "mail_status",
    "mail_error_message",
    "fatturapa_status",
    "fatturapa_error_message",
    "identificativo_sdi",
)


def omit_flat_lifecycle_fields(data):
    """Se c'è lifecycle, toglie i duplicati flat dal JSON."""
    if isinstance(data, dict) and data.get("lifecycle") is not None:
        for key in _FLAT_LIFECYCLE_RESPONSE_KEYS:
            data.pop(key, None)
    return data


class DocumentQuickStatusSchema(BaseModel):
    """Contratto FE colonna Stato rapido — esito intermediario FatturaPA."""

    mail_status: MailStatusLiteral = Field(
        None,
        description="Omesso dal JSON se `lifecycle` è presente (lifecycle.mail.status)",
    )
    mail_error_message: Optional[str] = Field(
        None,
        description="Omesso dal JSON se `lifecycle` è presente (lifecycle.mail.error_message)",
    )
    fatturapa_status: FatturapaStatusLiteral = Field(
        None,
        description=(
            "Omesso dal JSON se `lifecycle` è presente (lifecycle.fatturapa.status). "
            "Overlay calcolato: uploaded|sent|error|null. Non è copia di `status`."
        ),
    )
    fatturapa_error_message: Optional[str] = Field(
        None,
        description="Omesso dal JSON se `lifecycle` è presente (lifecycle.fatturapa.error_message)",
    )
    identificativo_sdi: Optional[str] = Field(
        None,
        description="Omesso dal JSON se `lifecycle` è presente (lifecycle.fatturapa.identificativo_sdi)",
    )
    lifecycle: Optional[FiscalDocumentLifecycleSchema] = Field(
        None,
        description="Stati per sottosistema (workflow + FatturaPA + SDI + mail)",
    )
