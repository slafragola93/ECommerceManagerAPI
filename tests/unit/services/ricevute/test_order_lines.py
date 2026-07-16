"""Test righe spedizione condivise ricevute."""
from decimal import Decimal
from types import SimpleNamespace

from src.services.ricevute.order_lines import (
    build_shipping_line_dict,
    load_product_weights,
    resolve_line_product_weight,
    resolve_order_total_weight,
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


def test_resolve_order_total_weight_from_order_details_when_header_zero():
    order = SimpleNamespace(total_weight=0)
    details = [
        SimpleNamespace(
            id_order_document=None,
            id_product=1,
            product_weight=Decimal("12.5"),
            product_qty=2,
        ),
        SimpleNamespace(
            id_order_document=None,
            id_product=2,
            product_weight=Decimal("1.0"),
            product_qty=1,
        ),
        SimpleNamespace(
            id_order_document=99,
            id_product=3,
            product_weight=Decimal("99"),
            product_qty=1,
        ),
    ]
    assert resolve_order_total_weight(order, details) == 26.0


def test_resolve_order_total_weight_from_product_catalog():
    order = SimpleNamespace(total_weight=0)
    details = [
        SimpleNamespace(
            id_order_document=None,
            id_product=10,
            product_weight=None,
            product_qty=2,
        ),
    ]
    catalog = {10: 3.25}
    assert resolve_order_total_weight(order, details, product_weights=catalog) == 6.5


def test_resolve_line_product_weight_prefers_order_detail():
    detail = SimpleNamespace(id_product=10, product_weight=Decimal("4.0"))
    assert resolve_line_product_weight(detail, {10: 9.0}) == 4.0


def test_resolve_order_total_weight_prefers_stored_order_value():
    order = SimpleNamespace(total_weight=Decimal("30.00"))
    details = [
        SimpleNamespace(id_order_document=None, product_weight=Decimal("1"), product_qty=1),
    ]
    assert resolve_order_total_weight(order, details) == 30.0


def test_resolve_order_total_weight_fallback_shipping():
    order = SimpleNamespace(total_weight=0)
    details = [
        SimpleNamespace(id_order_document=None, product_weight=None, product_qty=1),
    ]
    shipping = SimpleNamespace(weight=Decimal("26.45000"))
    assert resolve_order_total_weight(order, details, shipping) == 26.45
