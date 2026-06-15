from decimal import Decimal
from types import SimpleNamespace

from src.services.core.tool import calculate_order_totals, calculate_price_with_tax


def test_calculate_order_totals_accepts_decimal_tax_percentages():
    articolo = SimpleNamespace(
        product_weight=1.0,
        product_qty=2,
        product_price=100.0,
        id_tax=9,
        total_price_net=None,
        total_price_with_tax=None,
    )
    tax_percentages = {9: Decimal("22.00")}

    totals = calculate_order_totals([articolo], tax_percentages)

    assert totals["total_price"] == 200.0
    assert totals["total_price_with_tax"] == 244.0


def test_calculate_price_with_tax_accepts_decimal_inputs():
    result = calculate_price_with_tax(Decimal("100.00"), Decimal("22.00"), quantity=1)

    assert result == 122.0
