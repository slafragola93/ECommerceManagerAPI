from pydantic import BaseModel, Field


class PaymentSchema(BaseModel):
    name: str = Field(..., max_length=50)
    is_complete_payment: bool = Field(default=False)


class PaymentResponseSchema(BaseModel):
    name: str
    is_complete_payment: bool


class AllPaymentsResponseSchema(BaseModel):
    payments: list[PaymentResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
