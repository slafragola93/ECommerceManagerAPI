from typing import Optional

from pydantic import BaseModel, Field, validator

from .address_schema import AddressResponseSchema
from .customer_schema import CustomerResponseSchema

class OrderDocumentSchema(BaseModel):
    id_order: Optional[int] = 0
    id_address_delivery: Optional[int] = 0
    id_address_invoice: Optional[int] = 0
    id_customer: Optional[int] = 0
    id_sectional: int = Field(..., gt=0)
    id_shipping: int = Field(..., gt=0)
    document_number: int = Field(..., gt=0)
    type_document: str = Field(..., max_length=32)
    total_weight: Optional[float] = 0.0
    total_price_with_tax: Optional[float] = 0.0
    total_price_net: Optional[float] = 0.0
    total_discount: Optional[float] = 0.0
    is_invoice_requested: Optional[bool] = False
    note: Optional[str] = None


class OrderDocumentResponseSchema(BaseModel):
    id_order_document: int
    address_delivery: AddressResponseSchema | None
    address_invoice: AddressResponseSchema | None
    customer: CustomerResponseSchema | None
    sectional: str
    id_shipping: int
    document_number: int
    type_document: str
    total_weight: float
    total_price_with_tax: float
    total_price_net: float
    total_discount: float
    is_invoice_requested: bool
    note: str | None
    
    @validator('total_weight', 'total_price_with_tax', 'total_price_net', 'total_discount', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)


class AllOrderDocumentResponseSchema(BaseModel):
    order_documents: list[OrderDocumentResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
