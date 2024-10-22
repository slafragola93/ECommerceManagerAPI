from datetime import datetime, date
from typing import Optional
from .address_schema import AddressResponseSchema

from pydantic import BaseModel, Field


class InvoiceSchema(BaseModel):
    id_order: Optional[int] = None
    id_address_delivery: Optional[int] = 0
    id_address_invoice: Optional[int] = 0
    id_customer: int | None = Field(gt=-1)
    id_payment: int | None
    invoice_status: Optional[str] = Field(None, max_length=100)
    note: str = Field(max_length=100)
    document_number: Optional[int] = None
    payed: bool
    date_add: Optional[date] = None


class InvoiceResponseSchema(BaseModel):
    id_invoice: int
    id_order: Optional[int]
    address_delivery: AddressResponseSchema | None
    address_invoice: AddressResponseSchema | None
    id_customer: int | None
    id_payment: int | None
    payment_name: str | None
    invoice_status: str | None
    note: str | None
    document_number: int
    payed: bool
    date_add: datetime


class AllInvoiceResponseSchema(BaseModel):
    invoices: list[InvoiceResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
