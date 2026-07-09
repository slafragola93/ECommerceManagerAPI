"""Test righe spedizione condivise ricevute."""
from decimal import Decimal
from types import SimpleNamespace

from src.services.ricevute.order_lines import (
    build_shipping_line_dict,
    resolve_shipping_amounts,
)


def test_resolve_shipping_amounts_from_record():
    order = SimpleNamespace(
        products_total_price_with_tax=Decimal("122.00"),
        total_price_with_tax=Decimal("134.20"),
    )
    shipping = SimpleNamespace(price_tax_excl=Decimal("10.00"), price_tax_incl=Decimal("12.20"))
    net, incl = resolve_shipping_amounts(order, shipping)
    assert net == 10.0
    assert incl == 12.2


def test_resolve_shipping_amounts_fallback_from_order_delta():
    order = SimpleNamespace(
        products_total_price_with_tax=Decimal("122.00"),
        total_price_with_tax=Decimal("134.20"),
    )
    net, incl = resolve_shipping_amounts(order, None)
    assert incl == 12.2
    assert net == 12.2


def test_build_shipping_line_dict():
    order = SimpleNamespace(
        products_total_price_with_tax=Decimal("100.00"),
        total_price_with_tax=Decimal("112.20"),
    )
    shipping = SimpleNamespace(id_tax=3, price_tax_excl=Decimal("10.00"), price_tax_incl=Decimal("12.20"))
    line = build_shipping_line_dict(order, shipping)
    assert line is not None
    assert line["is_shipping"] is True
    assert line["product_name"] == "Spedizione"
    assert line["total_price_with_tax"] == 12.2
