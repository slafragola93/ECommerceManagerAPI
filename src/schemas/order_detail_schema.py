from typing import Optional

from pydantic import BaseModel, Field, validator


class OrderDetailSchema(BaseModel):
    id_order: Optional[int] = 0
    id_order_document: Optional[int] = 0
    id_origin: Optional[int] = 0
    id_tax: Optional[int] = 0
    id_product: Optional[int] = Field(None, ge=0)
    product_name: str = Field(..., max_length=100)
    product_reference: str = Field(..., max_length=100)
    product_qty: int = Field(..., ge=0)
    product_price: Optional[float] = 0.0
    product_weight: Optional[float] = 0.0
    reduction_percent: Optional[float] = 0.0
    reduction_amount: Optional[float] = 0.0
    note: Optional[str] = Field(None, max_length=200)


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
    note: Optional[str] = None
    img_url: Optional[str] = None  
    
    @validator('product_price', 'product_weight', 'reduction_percent', 'reduction_amount', pre=True, allow_reuse=True)
    def round_decimal(cls, v):
        if v is None:
            return None
        return round(float(v), 2)


class AllOrderDetailsResponseSchema(BaseModel):
    order_details: list[OrderDetailResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
