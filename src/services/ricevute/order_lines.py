"""Righe ordine e spedizione condivise tra API ricevute e PDF."""
from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy.orm import Session

from src.models.order import Order
from src.models.shipping import Shipping


def load_order_shipping(db: Session, order: Order) -> Optional[Shipping]:
    if not order.id_shipping:
        return None
    shipping = (
        db.query(Shipping).filter(Shipping.id_shipping == order.id_shipping).first()
    )
    if shipping:
        return shipping
    related = getattr(order, "shipments", None)
    if related is None:
        return None
    if isinstance(related, list):
        return related[0] if related else None
    return related


def _as_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)


def resolve_shipping_amounts(
    order: Order, shipping: Optional[Shipping] = None
) -> Tuple[float, float]:
    """Restituisce (netto, lordo) spedizione per ordine/ricevuta."""
    shipping_net = 0.0
    shipping_incl = 0.0
    if shipping:
        shipping_net = _as_float(shipping.price_tax_excl)
        shipping_incl = _as_float(shipping.price_tax_incl)

    products_gross = _as_float(order.products_total_price_with_tax)
    total_gross = _as_float(order.total_price_with_tax)
    if shipping_incl <= 0 and total_gross > products_gross:
        shipping_incl = max(total_gross - products_gross, 0.0)
    if shipping_net <= 0 and shipping_incl > 0:
        shipping_net = shipping_incl

    return round(shipping_net, 2), round(shipping_incl, 2)


def build_shipping_line_dict(
    order: Order,
    shipping: Optional[Shipping],
    *,
    product_name: str = "Spedizione",
) -> Optional[dict]:
    shipping_net, shipping_incl = resolve_shipping_amounts(order, shipping)
    if shipping_net <= 0 and shipping_incl <= 0:
        return None
    return {
        "id_order_detail": 0,
        "id_product": None,
        "product_name": product_name,
        "product_reference": "-",
        "product_qty": 1,
        "id_tax": shipping.id_tax if shipping else None,
        "unit_price_net": shipping_net,
        "unit_price_with_tax": shipping_incl,
        "total_price_net": shipping_net,
        "total_price_with_tax": shipping_incl,
        "reduction_percent": 0.0,
        "reduction_amount": 0.0,
        "is_shipping": True,
    }
