from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrderPaymentCreateSchema(BaseModel):
    id_payment: int = Field(..., gt=0, description="ID metodo di pagamento (catalogo payments)")
    amount: float = Field(..., gt=0, description="Importo del pagamento")
    is_paid: bool = Field(default=False, description="True se già incassato")
    payment_date: Optional[date] = Field(
        default=None,
        description="Data incasso (se is_paid=true e omessa, usa oggi)",
    )
    note: Optional[str] = Field(default=None, max_length=200)


class OrderPaymentUpdateSchema(BaseModel):
    id_payment: Optional[int] = Field(default=None, gt=0)
    amount: Optional[float] = Field(default=None, gt=0)
    note: Optional[str] = Field(default=None, max_length=200)


class OrderPaymentPaidStatusSchema(BaseModel):
    is_paid: bool
    payment_date: Optional[date] = None


class OrderPaymentResponseSchema(BaseModel):
    id_order_payment: int
    id_order: int
    id_payment: int
    amount: float
    is_paid: bool
    payment_date: Optional[date] = None
    note: Optional[str] = None
    date_add: Optional[datetime] = None
    payment: Optional[dict] = None

    @field_validator("amount", mode="before")
    @classmethod
    def round_amount(cls, v):
        if v is None:
            return v
        return round(float(v), 5)

    model_config = ConfigDict(from_attributes=True)


class OrderPaymentSummarySchema(BaseModel):
    total_scheduled: float = 0.0
    total_paid: float = 0.0
    remaining_amount: float = 0.0


class OrderPaymentsListResponseSchema(BaseModel):
    order_payments: List[OrderPaymentResponseSchema]
    payment_summary: OrderPaymentSummarySchema
    total: int
