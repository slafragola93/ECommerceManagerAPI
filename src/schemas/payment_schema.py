from typing import Optional
from pydantic import BaseModel, Field


class PaymentSchema(BaseModel):
    id_store: Optional[int] = None
    name: str = Field(..., max_length=50)
    is_complete_payment: bool = Field(default=False)
    fiscal_mode_payment: str = Field(default='MP05')


class PaymentResponseSchema(BaseModel):
    id_payment: int
    name: str
    is_complete_payment: bool
    fiscal_mode_payment: Optional[str] = None

    class Config:
        from_attributes = True
class AllPaymentsResponseSchema(BaseModel):
    payments: list[PaymentResponseSchema]
    total: int
    page: int
    limit: int


class ConfigDict:
    from_attributes = True
