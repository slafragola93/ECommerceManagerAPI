from typing import Optional

from pydantic import BaseModel, Field

from .tax_schema import TaxResponseSchema
from .address_schema import AddressResponseSchema
from .customer_schema import CustomerResponseSchema

class OrderDocumentSchema(BaseModel):
    id_order: Optional[int] = 0
    id_tax: Optional[int] = 0
    id_address_delivery: Optional[int] = 0
    id_address_invoice: Optional[int] = 0
    id_customer: Optional[int] = 0
    id_sectional: int = Field(..., gt=0)
    document_number: str = Field(..., max_length=32)
    type_document: str = Field(..., max_length=32)
    total_weight: Optional[float] = 0.0
    total_price: Optional[float] = 0.0
    delivery_price: Optional[float] = 0.0
    note: Optional[str] = None


class OrderDocumentResponseSchema(BaseModel):
    id_order_document: int
    tax: TaxResponseSchema | None
    address_delivery: AddressResponseSchema | None
    address_invoice: AddressResponseSchema | None
    customer: CustomerResponseSchema | None
    sectional: str
    document_number: str
    type_document: str
    total_weight: float
    total_price: float
    delivery_price: float
    note: str | None


class AllOrderDocumentResponseSchema(BaseModel):
    order_documents: list[OrderDocumentResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
