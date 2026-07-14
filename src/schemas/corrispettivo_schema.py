from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_serializer


class CorrispettivoFiltersSchema(BaseModel):
    id_platform: Optional[int] = Field(None, gt=0)
    id_store: Optional[int] = Field(None, gt=0)
    delivery_country_iso: Optional[str] = Field(None, min_length=2, max_length=5)
    day: Optional[int] = Field(None, ge=1, le=31)


class CorrispettivoAmountSchema(BaseModel):
    sales_net: Decimal = Decimal("0")
    returns_net: Decimal = Decimal("0")
    net: Decimal = Decimal("0")

    @field_serializer("sales_net", "returns_net", "net")
    def serialize_decimal(self, value: Decimal) -> float:
        return round(float(value), 2)


class CorrispettivoTaxColumnSchema(BaseModel):
    id_tax: int
    label: str
    percentage: Optional[float] = None


class CorrispettivoShippingDaySchema(CorrispettivoAmountSchema):
    """Spedizione giornaliera — stesso contratto delle celle aliquota (sales/returns/net)."""


class CorrispettivoRiepilogoRowSchema(BaseModel):
    day: int
    date: date
    cells: Dict[str, CorrispettivoAmountSchema]
    row_net: CorrispettivoAmountSchema
    shipping: CorrispettivoShippingDaySchema


class CorrispettivoSplitTotalsSchema(BaseModel):
    total_with_tax: Decimal = Decimal("0")
    total_net: Decimal = Decimal("0")
    products_with_tax: Decimal = Decimal("0")
    products_net: Decimal = Decimal("0")
    shipping_with_tax: Decimal = Decimal("0")
    shipping_net: Decimal = Decimal("0")
    order_count: int = 0
    return_count: int = 0

    @field_serializer(
        "total_with_tax",
        "total_net",
        "products_with_tax",
        "products_net",
        "shipping_with_tax",
        "shipping_net",
    )
    def serialize_decimal(self, value: Decimal) -> float:
        return round(float(value), 2)


class CorrispettivoSalesBreakdownSchema(BaseModel):
    """Scomposizione vendite lorde per audit ricevute (BE-3.2)."""

    base: CorrispettivoSplitTotalsSchema
    ricevute_decurtazione: CorrispettivoSplitTotalsSchema
    ricevute_imputazione: CorrispettivoSplitTotalsSchema


class CorrispettivoDaySummarySchema(BaseModel):
    date: date
    sales: CorrispettivoSplitTotalsSchema
    returns: CorrispettivoSplitTotalsSchema
    net: CorrispettivoSplitTotalsSchema
    sales_breakdown: Optional[CorrispettivoSalesBreakdownSchema] = None


class CorrispettivoRiepilogoResponseSchema(BaseModel):
    year: int
    month: int
    calculation_mode: str = "order_document_date"
    timezone: str = "Europe/Rome"
    delivery_country_iso: Optional[str] = None
    columns: List[CorrispettivoTaxColumnSchema]
    rows: List[CorrispettivoRiepilogoRowSchema]
    month_totals: CorrispettivoAmountSchema


class CorrispettivoListResponseSchema(BaseModel):
    year: int
    month: int
    timezone: str = "Europe/Rome"
    days: List[CorrispettivoDaySummarySchema]
    month_totals: CorrispettivoSplitTotalsSchema


class CorrispettivoExportRequestSchema(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)
    filters: Optional[CorrispettivoFiltersSchema] = None
