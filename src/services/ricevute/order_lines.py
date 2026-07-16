"""Righe ordine e spedizione condivise tra API ricevute e PDF."""
from __future__ import annotations

from typing import Iterable, Mapping, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from src.models.order import Order
from src.models.product import Product
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


def load_product_weights(session: Session, product_ids: Iterable[int]) -> dict[int, float]:
    """Pesi catalogo per id_product (kg)."""
    ids = {int(pid) for pid in product_ids if pid}
    if not ids:
        return {}
    rows = (
        session.query(Product.id_product, Product.weight)
        .filter(Product.id_product.in_(ids))
        .all()
    )
    weights: dict[int, float] = {}
    for row in rows:
        if row.weight is None:
            continue
        weight = float(row.weight)
        if weight > 0:
            weights[row.id_product] = weight
    return weights


def resolve_line_product_weight(
    detail: object,
    product_weights: Optional[Mapping[int, float]] = None,
) -> Optional[float]:
    """Peso unitario riga: order_detail.product_weight, altrimenti products.weight."""
    line_weight = getattr(detail, "product_weight", None)
    if line_weight is not None:
        weight = float(line_weight)
        if weight > 0:
            return weight
    id_product = getattr(detail, "id_product", None)
    if id_product and product_weights:
        catalog_weight = product_weights.get(int(id_product))
        if catalog_weight and catalog_weight > 0:
            return catalog_weight
    return None


def resolve_order_total_weight(
    order: Order,
    order_details: Sequence[object],
    shipping: Optional[Shipping] = None,
    product_weights: Optional[Mapping[int, float]] = None,
) -> Optional[float]:
    """
    Peso totale ordine (kg) per ricevuta/PDF.

    1. `orders.total_weight` se valorizzato (> 0)
    2. Somma live peso riga × qty (order_detail.product_weight o products.weight)
    3. Fallback `shipping.weight`
    """
    stored = _as_float(getattr(order, "total_weight", None), default=0.0)
    if stored > 0:
        return round(stored, 2)

    total = 0.0
    has_line_weight = False
    for detail in order_details:
        if getattr(detail, "id_order_document", None):
            continue
        product_weight = resolve_line_product_weight(detail, product_weights)
        if product_weight is None:
            continue
        has_line_weight = True
        qty = getattr(detail, "product_qty", None) or 0
        total += product_weight * qty

    if has_line_weight and total > 0:
        return round(total, 2)

    if shipping and shipping.weight:
        shipping_weight = float(shipping.weight)
        if shipping_weight > 0:
            return round(shipping_weight, 2)

    return None


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
