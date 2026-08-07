"""Envelope comune per liste nested documenti collegati all'ordine.

Contratto target: ``{ items, total }`` (+ ``page``/``limit`` se paginato).
In transizione restano alias legacy (``returns`` / ``invoices`` / ``ricevute``).
"""
from typing import List

from pydantic import BaseModel, Field, model_validator

from src.schemas.fiscal_document_schema import InvoiceResponseSchema
from src.schemas.return_schema import ReturnResponseSchema
from src.schemas.ricevuta_schema import RicevutaListItemSchema


class OrderNestedDocumentsListSchema(BaseModel):
    """Base envelope ``items`` + ``total`` con paginazione opzionale."""

    items: List = Field(default_factory=list, description="Elementi della collection")
    total: int = Field(..., ge=0, description="Totale elementi (anche senza paginazione)")
    page: int = Field(1, ge=1, description="Pagina corrente")
    limit: int = Field(10, ge=1, description="Elementi per pagina")


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


class OrderInvoicesListResponseSchema(OrderNestedDocumentsListSchema):
    """Lista fatture nested: ``GET /orders/{id}/invoices``."""

    items: List[InvoiceResponseSchema] = Field(default_factory=list)
    invoices: List[InvoiceResponseSchema] = Field(
        default_factory=list,
        deprecated=True,
        description="Alias legacy di ``items`` (deprecated)",
    )

    @model_validator(mode="after")
    def _sync_alias(self):
        if self.items and not self.invoices:
            object.__setattr__(self, "invoices", list(self.items))
        elif self.invoices and not self.items:
            object.__setattr__(self, "items", list(self.invoices))
        return self


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
