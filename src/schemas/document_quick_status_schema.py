"""Campi stati rapidi condivisi (lista + dettaglio documenti)."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

FatturapaStatusLiteral = Optional[Literal["uploaded", "sent", "error"]]
MailStatusLiteral = Optional[Literal["sent", "pending", "error"]]


class DocumentQuickStatusSchema(BaseModel):
    """Contratto FE colonna Stato rapido — esito intermediario FatturaPA."""

    mail_status: MailStatusLiteral = Field(
        None,
        description="sent|pending|error|null — invio email documento",
    )
    mail_error_message: Optional[str] = Field(
        None, description="Solo se mail_status=error"
    )
    fatturapa_status: FatturapaStatusLiteral = Field(
        None,
        description=(
            "uploaded|sent|error|null — esito FatturaPA.com "
            "(non notifiche SDI RC/NS)"
        ),
    )
    fatturapa_error_message: Optional[str] = Field(
        None, description="Solo se fatturapa_status=error"
    )
    identificativo_sdi: Optional[str] = Field(
        None, description="ID SdI se disponibile (POOL o upload_result)"
    )
