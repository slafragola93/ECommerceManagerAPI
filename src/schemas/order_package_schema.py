from typing import Optional
from pydantic import BaseModel, Field


class OrderPackageSchema(BaseModel):

    id_order: Optional[int] = None
    id_order_document: Optional[int] = None
    height: float
    width: float
    depth: float
    weight: float
    length: float
    value: float = Field(default=0.0)


class OrderPackageResponseSchema(BaseModel):
    id_order_package: int
    id_order: Optional[int] = None
    id_order_document: Optional[int] = None
    height: float
    width: float
    depth: float
    weight: float
    length: float
    value: float


class ConfigDict:
    from_attributes = True
