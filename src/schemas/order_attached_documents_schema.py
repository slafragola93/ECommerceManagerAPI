"""Envelope per liste nested documenti collegati all'ordine.

Resi e ricevute: ``{ items, total }`` + alias legacy (``returns`` / ``ricevute``).
Fatture: sola chiave ``invoices`` (niente ``items``).
"""
from typing import List

from pydantic import BaseModel, Field, model_validator

from src.schemas.fiscal_document_schema import InvoiceResponseSchema
from src.schemas.return_schema import ReturnResponseSchema
from src.schemas.ricevuta_schema import RicevutaListItemSchema


class OrderNestedListMetaSchema(BaseModel):
    """Paginazione comune (senza chiave collection)."""

    total: int = Field(..., ge=0, description="Totale elementi (anche senza paginazione)")
    page: int = Field(1, ge=1, description="Pagina corrente")
    limit: int = Field(10, ge=1, description="Elementi per pagina")


class OrderNestedDocumentsListSchema(OrderNestedListMetaSchema):
    """Base envelope ``items`` + ``total`` con paginazione opzionale."""

    items: List = Field(default_factory=list, description="Elementi della collection")


class OrderReturnsListResponseSchema(OrderNestedDocumentsListSchema):
    """Lista resi nested: ``GET /orders/{id}/returns``."""

    items: List[ReturnResponseSchema] = Field(default_factory=list)
    returns: List[ReturnResponseSchema] = Field(
        default_factory=list,
        deprecated=True,
        description="Alias legacy di ``items`` (deprecated)",
    )

    @model_validator(mode="after")
    def _sync_alias(self):
        if self.items and not self.returns:
            object.__setattr__(self, "returns", list(self.items))
        elif self.returns and not self.items:
            object.__setattr__(self, "items", list(self.returns))
        return self


class OrderInvoicesListResponseSchema(OrderNestedListMetaSchema):
    """Lista fatture nested: ``GET /orders/{id}/invoices``.

    Una sola chiave collection: ``invoices`` (niente ``items``).
    """

    invoices: List[InvoiceResponseSchema] = Field(
        default_factory=list,
        description="Fatture dell'ordine",
    )


class OrderRicevuteListResponseSchema(OrderNestedDocumentsListSchema):
    """Lista ricevute nested: ``GET /orders/{id}/ricevute``."""

    items: List[RicevutaListItemSchema] = Field(default_factory=list)
    ricevute: List[RicevutaListItemSchema] = Field(
        default_factory=list,
        deprecated=True,
        description="Alias legacy di ``items`` (deprecated)",
    )

    @model_validator(mode="after")
    def _sync_alias(self):
        if self.items and not self.ricevute:
            object.__setattr__(self, "ricevute", list(self.items))
        elif self.ricevute and not self.items:
            object.__setattr__(self, "items", list(self.ricevute))
        return self
