from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class InvoiceSchema(BaseModel):
    id_order: int = Field(..., gt=0)
    document_number: str = Field(..., max_length=10)
    filename: str = Field(..., max_length=255)
    xml_content: Optional[str] = None
    status: str = Field(default="pending", max_length=50)
    upload_result: Optional[str] = None


class InvoiceUpdateSchema(BaseModel):
    status: Optional[str] = Field(None, max_length=50)
    upload_result: Optional[str] = None


class InvoiceResponseSchema(BaseModel):
    id_invoice: int
    id_order: int
    document_number: str
    filename: str
    status: str
    upload_result: Optional[str] = None
    date_add: Optional[datetime] = None
    date_upd: Optional[datetime] = None

    class Config:
        from_attributes = True


class AllInvoicesResponseSchema(BaseModel):
    invoices: List[InvoiceResponseSchema]
    total: int
    page: int
    limit: int


class InvoiceIssuingRequestSchema(BaseModel):
    iso_code: str = Field(default="IT", max_length=2)
    send_to_sdi: bool = Field(default=False, description="Se true, invia la fattura al Sistema di Interscambio")


class InvoiceIssuingResponseSchema(BaseModel):
    status: str
    message: str
    invoice_id: Optional[int] = None
    document_number: Optional[str] = None
    filename: Optional[str] = None
    upload_result: Optional[dict] = None


class InvoiceXMLResponseSchema(BaseModel):
    status: str
    message: str
    order_id: int
    document_number: str
    filename: str
    xml_content: str
    xml_size: int