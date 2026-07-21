import calendar
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_serializer, model_validator


def validate_corrispettivo_day(year: int, month: int, day: int) -> None:
    """Verifica che il giorno esista nel mese indicato."""
    last_day = calendar.monthrange(year, month)[1]
    if day > last_day:
        raise ValueError(
            f"Giorno {day} non valido per {month:02d}/{year} (massimo {last_day})"
        )


class CorrispettivoFiltersSchema(BaseModel):
    id_platform: Optional[int] = Field(None, gt=0)
    id_store: Optional[int] = Field(None, gt=0)
    delivery_country_iso: Optional[str] = Field(None, min_length=2, max_length=5)
    day: Optional[int] = Field(None, ge=1, le=31)


class CorrispettivoTaxCellSchema(BaseModel):
    """Importi per aliquota — sempre con IVA inclusa."""

    products_sales: Decimal = Decimal("0")
    shipping_sales: Decimal = Decimal("0")
    products_returns: Decimal = Decimal("0")
    shipping_returns: Decimal = Decimal("0")

    @field_serializer(
        "products_sales",
        "shipping_sales",
        "products_returns",
        "shipping_returns",
    )
    def serialize_decimal(self, value: Decimal) -> float:
        return round(float(value), 2)


class CorrispettivoRiepilogoTotalsSchema(CorrispettivoTaxCellSchema):
    row_total: Decimal = Decimal("0")

    @field_serializer("row_total")
    def serialize_row_total(self, value: Decimal) -> float:
        return round(float(value), 2)


class CorrispettivoTaxColumnSchema(BaseModel):
    id_tax: int
    label: str
    percentage: Optional[float] = None


class CorrispettivoRiepilogoRowSchema(BaseModel):
    day: int
    date: date
    cells: Dict[str, CorrispettivoTaxCellSchema]
    row_total: Decimal = Decimal("0")

    @field_serializer("row_total")
    def serialize_row_total(self, value: Decimal) -> float:
        return round(float(value), 2)


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
    day: Optional[int] = None
    calculation_mode: str = "order_document_date"
    timezone: str = "Europe/Rome"
    delivery_country_iso: Optional[str] = None
    columns: List[CorrispettivoTaxColumnSchema]
    rows: List[CorrispettivoRiepilogoRowSchema]
    month_totals: CorrispettivoRiepilogoTotalsSchema


class CorrispettivoListResponseSchema(BaseModel):
    year: int
    month: int
    day: Optional[int] = None
    timezone: str = "Europe/Rome"
    days: List[CorrispettivoDaySummarySchema]
    month_totals: CorrispettivoSplitTotalsSchema


class CorrispettivoExportRequestSchema(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)
    filters: Optional[CorrispettivoFiltersSchema] = None

    @model_validator(mode="after")
    def validate_filter_day(self):
        if self.filters and self.filters.day is not None:
            validate_corrispettivo_day(self.year, self.month, self.filters.day)
        return self


class CorrispettivoDayExportRequestSchema(BaseModel):
    """Export corrispettivo ristretto a un singolo giorno del mese."""

    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)
    filters: Optional[CorrispettivoFiltersSchema] = None

    @model_validator(mode="after")
    def validate_calendar_day(self):
        validate_corrispettivo_day(self.year, self.month, self.day)
        if self.filters and self.filters.day is not None and self.filters.day != self.day:
            raise ValueError("filters.day deve coincidere con day quando entrambi sono valorizzati")
        return self

    def to_export_request(self) -> CorrispettivoExportRequestSchema:
        base = self.filters.model_dump(exclude_none=True) if self.filters else {}
        base.pop("day", None)
        merged_filters = CorrispettivoFiltersSchema(**base, day=self.day)
        return CorrispettivoExportRequestSchema(
            year=self.year,
            month=self.month,
            filters=merged_filters,
        )
