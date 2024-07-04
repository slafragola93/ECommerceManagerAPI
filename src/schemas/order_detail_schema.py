from typing import Optional

from pydantic import BaseModel, Field


class OrderDetailSchema(BaseModel):
    id_order: Optional[int] = 0
    id_invoice: Optional[int] = 0
    id_order_document: Optional[int] = 0
    id_origin: Optional[int] = 0
    id_tax: Optional[int] = 0
    id_product: int = Field(..., gt=0)
    product_name: str = Field(..., max_length=100)
    product_reference: str = Field(..., max_length=100)
    product_qty: int = Field(..., ge=0)
    product_price: Optional[float] = 0.0
    product_weight: Optional[float] = 0.0
    reduction_percent: Optional[float] = 0.0
    reduction_amount: Optional[float] = 0.0
    real_price: bool = False
    real_weight: bool = False


class OrderDetailResponseSchema(BaseModel):
    id_order_detail: int
    id_order: int
    id_order_document: int
    id_origin: int
    id_tax: int
    id_product: int
    product_name: str
    product_reference: str
    product_qty: int
    product_price: float
    product_weight: float
    reduction_percent: float
    reduction_amount: float


class AllOrderDetailsResponseSchema(BaseModel):
    order_details: list[OrderDetailResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
