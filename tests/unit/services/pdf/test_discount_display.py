"""Unit test helper sconti PDF condiviso."""
from src.services.pdf.discount_display import (
    format_discount_label,
    resolve_line_discount,
)


def _fmt_num(value, decimals=2):
    v = float(value or 0)
    formatted = f"{v:,.{decimals}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_pct(value):
    return f"{_fmt_num(value, 2)} %"


class TestResolveLineDiscount:
    def test_from_percent(self):
        amount, pct = resolve_line_discount(
            qty=2,
            unit_net=100.0,
            line_net=180.0,
            reduction_percent=10.0,
            reduction_amount=0.0,
        )
        assert amount == 20.0
        assert pct == 10.0

    def test_from_amount(self):
        amount, pct = resolve_line_discount(
            qty=1,
            unit_net=2565.57,
            line_net=2065.57,
            reduction_percent=0.0,
            reduction_amount=500.0,
        )
        assert amount == 500.0
        assert pct == 500.0 / 2565.57 * 100.0

    def test_derived_from_totals(self):
        amount, pct = resolve_line_discount(
            qty=1,
            unit_net=2565.57,
            line_net=2065.57,
            reduction_percent=0.0,
            reduction_amount=0.0,
        )
        assert amount == 500.0


class TestFormatDiscountLabel:
    def test_percent_shows_pct(self):
        label = format_discount_label(
            reduction_percent=12.5,
            discount_amount=100.0,
            fmt_num=_fmt_num,
            fmt_pct=_fmt_pct,
        )
        assert label == "12,50 %"

    def test_amount_shows_cifra(self):
        label = format_discount_label(
            reduction_percent=0.0,
            discount_amount=500.0,
            fmt_num=_fmt_num,
            fmt_pct=_fmt_pct,
        )
        assert label == "500,00"

    def test_zero(self):
        label = format_discount_label(
            reduction_percent=0.0,
            discount_amount=0.0,
            fmt_num=_fmt_num,
            fmt_pct=_fmt_pct,
        )
        assert label == "0,00 %"
