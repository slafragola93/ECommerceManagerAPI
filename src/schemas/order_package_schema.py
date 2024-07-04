from pydantic import BaseModel, Field


class OrderPackageSchema(BaseModel):

    id_order: int
    height: float
    width: float
    depth: float
    weight: float
    value: float = Field(default=0.0)


class OrderPackageResponseSchema(BaseModel):
    id_order_package: int
    id_order: int
    height: float
    width: float
    depth: float
    weight: float
    value: float


class ConfigDict:
    from_attributes = True
