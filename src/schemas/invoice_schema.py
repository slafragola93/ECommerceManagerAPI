from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, Field


class InvoiceSchema(BaseModel):
    id_order: Optional[int] = None
    id_address_delivery: int = Field(gt=-1)
    id_address_invoice: int = Field(gt=-1)
    id_customer: int = Field(gt=-1)
    id_payment: int
    invoice_status: Optional[str] = Field(None, max_length=100)
    note: str = Field(max_length=100)
    document_number: Optional[int] = None
    payed: bool
    date_add: Optional[date] = None


class InvoiceResponseSchema(BaseModel):
    id_invoice: int
    id_order: Optional[int]
    id_address_delivery: int = Field(gt=-1)
    id_address_invoice: int = Field(gt=-1)
    id_customer: int = Field(gt=-1)
    id_payment: Optional[int]
    payment_name: Optional[str]
    invoice_status: Optional[str] = Field(None, min_length=1, max_length=100)
    note: str = Field(max_length=100)
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
