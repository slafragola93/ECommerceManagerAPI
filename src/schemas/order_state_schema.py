from pydantic import BaseModel, Field


class OrderStateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class OrderStateResponseSchema(BaseModel):
    id_order_state: int
    name: str


class AllOrdersStateResponseSchema(BaseModel):
    states: list[OrderStateResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
