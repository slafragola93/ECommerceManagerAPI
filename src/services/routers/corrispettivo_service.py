from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.repository.corrispettivo_repository import CorrispettivoRepository
from src.schemas.corrispettivo_schema import (
    CorrispettivoAmountSchema,
    CorrispettivoDaySummarySchema,
    CorrispettivoExportRequestSchema,
    CorrispettivoFiltersSchema,
    CorrispettivoListResponseSchema,
    CorrispettivoRiepilogoResponseSchema,
    CorrispettivoRiepilogoRowSchema,
    CorrispettivoShippingDaySchema,
    CorrispettivoSplitTotalsSchema,
    CorrispettivoTaxColumnSchema,
)
from src.services.corrispettivi.aggregation import (
    aggregate_matrix,
    build_month_totals,
    build_riepilogo_rows,
    build_tax_columns,
    tax_column_label,
)
from src.services.export.corrispettivi_excel_service import CorrispettiviExcelService


class CorrispettivoService:
    def __init__(self, session: Session):
        self._repository = CorrispettivoRepository(session)

    @staticmethod
    def _filters_to_dict(filters: Optional[CorrispettivoFiltersSchema]) -> Optional[dict]:
        if not filters:
            return None
        data = filters.model_dump(exclude_none=True)
        return data or None

    def get_riepilogo(
        self,
        year: int,
        month: int,
        filters: Optional[CorrispettivoFiltersSchema] = None,
    ) -> CorrispettivoRiepilogoResponseSchema:
        filter_dict = self._filters_to_dict(filters)
        country_iso = filter_dict.get("delivery_country_iso") if filter_dict else None
        movements = self._repository.fetch_movements(year, month, filter_dict)
        product_buckets, shipping_buckets = aggregate_matrix(movements, country_iso=country_iso)
        taxes_by_id = self._repository.get_taxes_by_ids(
            {
                tax_id
                for day_buckets in product_buckets.values()
                for tax_id in day_buckets.keys()
            }
        )
        rows_data, tax_ids = build_riepilogo_rows(product_buckets, shipping_buckets, taxes_by_id)
        columns = build_tax_columns(tax_ids, taxes_by_id)

        rows = [
            CorrispettivoRiepilogoRowSchema(
                day=row["day"],
                date=row["date"],
                cells={
                    key: CorrispettivoAmountSchema(**values)
                    for key, values in row["cells"].items()
                },
                row_net=CorrispettivoAmountSchema(**row["row_net"]),
                shipping=CorrispettivoShippingDaySchema(**row["shipping"]),
            )
            for row in rows_data
        ]

        return CorrispettivoRiepilogoResponseSchema(
            year=year,
            month=month,
            delivery_country_iso=country_iso,
            columns=[CorrispettivoTaxColumnSchema(**column) for column in columns],
            rows=rows,
            month_totals=CorrispettivoAmountSchema(**build_month_totals(rows_data)),
        )

    def get_daily_summary(
        self,
        year: int,
        month: int,
        filters: Optional[CorrispettivoFiltersSchema] = None,
    ) -> CorrispettivoListResponseSchema:
        filter_dict = self._filters_to_dict(filters)
        daily_counts = self._repository.fetch_daily_counts(year, month, filter_dict)
        gross_totals = self._repository.fetch_daily_gross_totals(year, month, filter_dict)

        days: list[CorrispettivoDaySummarySchema] = []
        month_net = CorrispettivoSplitTotalsSchema()

        for movement_date in sorted(gross_totals.keys()):
            bucket = gross_totals[movement_date]
            sales_data = bucket.get("sales", {})
            returns_data = bucket.get("returns", {})
            order_count, return_count = daily_counts.get(movement_date, (0, 0))

            sales = CorrispettivoSplitTotalsSchema(
                total_with_tax=sales_data.get("total_with_tax", 0),
                total_net=sales_data.get("total_net", 0),
                products_with_tax=sales_data.get("products_with_tax", 0),
                products_net=sales_data.get("products_net", 0),
                shipping_with_tax=sales_data.get("shipping_with_tax", 0),
                shipping_net=sales_data.get("shipping_net", 0),
                order_count=order_count,
            )
            returns = CorrispettivoSplitTotalsSchema(
                total_with_tax=returns_data.get("total_with_tax", 0),
                total_net=returns_data.get("total_net", 0),
                products_with_tax=returns_data.get("products_with_tax", 0),
                products_net=returns_data.get("products_net", 0),
                shipping_with_tax=returns_data.get("shipping_with_tax", 0),
                shipping_net=returns_data.get("shipping_net", 0),
                return_count=return_count,
            )
            net = CorrispettivoSplitTotalsSchema(
                total_with_tax=sales.total_with_tax - returns.total_with_tax,
                total_net=sales.total_net - returns.total_net,
                products_with_tax=sales.products_with_tax - returns.products_with_tax,
                products_net=sales.products_net - returns.products_net,
                shipping_with_tax=sales.shipping_with_tax - returns.shipping_with_tax,
                shipping_net=sales.shipping_net - returns.shipping_net,
            )

            days.append(
                CorrispettivoDaySummarySchema(
                    date=movement_date,
                    sales=sales,
                    returns=returns,
                    net=net,
                )
            )

            month_net.total_with_tax += net.total_with_tax
            month_net.total_net += net.total_net
            month_net.products_with_tax += net.products_with_tax
            month_net.products_net += net.products_net
            month_net.shipping_with_tax += net.shipping_with_tax
            month_net.shipping_net += net.shipping_net
            month_net.order_count += sales.order_count
            month_net.return_count += returns.return_count

        return CorrispettivoListResponseSchema(
            year=year,
            month=month,
            days=days,
            month_totals=month_net,
        )

    def build_export_zip(self, request: CorrispettivoExportRequestSchema) -> bytes:
        filter_dict = self._filters_to_dict(request.filters)
        country_codes = self._repository.list_country_codes_with_movements(
            request.year, request.month, filter_dict
        )

        riepilogo_all = self.get_riepilogo(request.year, request.month, request.filters)
        riepilogo_by_country = {}
        base_filter_data = request.filters.model_dump(exclude_none=True) if request.filters else {}
        for iso in country_codes:
            country_filters = CorrispettivoFiltersSchema(
                **{**base_filter_data, "delivery_country_iso": iso}
            )
            riepilogo_by_country[iso] = self.get_riepilogo(
                request.year,
                request.month,
                country_filters,
            )

        excel_service = CorrispettiviExcelService()
        return excel_service.build_registri_zip(
            consolidated=riepilogo_all,
            by_country=riepilogo_by_country,
        )
