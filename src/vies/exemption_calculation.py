"""
Calcolo esenzione VIES reale: sottrae l'IVA da righe e spedizione (lordo → netto a 0%).

Usato da apply-vies-exemption e da POST /orders con vies_status=eligible.
Non usare in sync PrestaShop.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.models.address import Address
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.shipping import Shipping
from src.repository.tax_repository import TaxRepository
from src.services.core.tool import calculate_price_without_tax


def get_order_delivery_country_id(session: Session, order: Order) -> Optional[int]:
    if not order.id_address_delivery:
        return None
    address = (
        session.query(Address)
        .filter(Address.id_address == order.id_address_delivery)
        .first()
    )
    if address and address.id_country and address.id_country > 0:
        return address.id_country
    return None


def resolve_source_tax_percentage(
    session: Session,
    id_tax: Optional[int],
    id_country_delivery: Optional[int],
) -> float:
    """
    Percentuale IVA da usare per ricavare il netto prima dell'esenzione:
    id_tax della riga/spedizione, else default paese, else default globale, else 0%.
    """
    repo = TaxRepository(session)
    if id_tax:
        tax = repo.get_tax_by_id(id_tax)
        if tax is not None and tax.percentage is not None:
            return float(tax.percentage)
    if id_country_delivery and id_country_delivery > 0:
        country_tax = repo.get_default_by_country(id_country_delivery)
        if country_tax is not None and country_tax.percentage is not None:
            return float(country_tax.percentage)
    global_tax = repo.get_global_default()
    if global_tax is not None and global_tax.percentage is not None:
        return float(global_tax.percentage)
    return 0.0


def _net_from_gross(gross: Optional[float], tax_percentage: float) -> float:
    if gross is None:
        return 0.0
    return calculate_price_without_tax(float(gross), tax_percentage)


def apply_vies_prices_to_detail_fields(
    *,
    unit_price_with_tax: Optional[float],
    total_price_with_tax: Optional[float],
    product_qty: Optional[int],
    source_tax_percentage: float,
) -> Dict[str, float]:
    """
    Ricava netto reale dal lordo e restituisce prezzi a 0% IVA (net = lordo).
    """
    qty = product_qty or 1
    total_gross = float(total_price_with_tax or 0.0)
    if total_gross == 0.0 and unit_price_with_tax is not None:
        total_gross = float(unit_price_with_tax) * qty

    unit_gross = (
        float(unit_price_with_tax)
        if unit_price_with_tax is not None
        else (total_gross / qty if qty else 0.0)
    )

    unit_net = _net_from_gross(unit_gross, source_tax_percentage)
    total_net = _net_from_gross(total_gross, source_tax_percentage)

    return {
        "unit_price_net": round(unit_net, 2),
        "unit_price_with_tax": round(unit_net, 2),
        "total_price_net": round(total_net, 2),
        "total_price_with_tax": round(total_net, 2),
    }


def apply_vies_prices_to_detail_dict(
    detail_data: Dict[str, Any],
    source_tax_percentage: float,
    vies_tax_id: int,
) -> Dict[str, Any]:
    prices = apply_vies_prices_to_detail_fields(
        unit_price_with_tax=detail_data.get("unit_price_with_tax"),
        total_price_with_tax=detail_data.get("total_price_with_tax"),
        product_qty=detail_data.get("product_qty"),
        source_tax_percentage=source_tax_percentage,
    )
    detail_data.update(prices)
    detail_data["id_tax"] = vies_tax_id
    return detail_data


def apply_vies_prices_to_order_detail(
    order_detail: OrderDetail,
    source_tax_percentage: float,
    vies_tax_id: int,
) -> None:
    prices = apply_vies_prices_to_detail_fields(
        unit_price_with_tax=order_detail.unit_price_with_tax,
        total_price_with_tax=order_detail.total_price_with_tax,
        product_qty=order_detail.product_qty,
        source_tax_percentage=source_tax_percentage,
    )
    order_detail.id_tax = vies_tax_id
    order_detail.unit_price_net = prices["unit_price_net"]
    order_detail.unit_price_with_tax = prices["unit_price_with_tax"]
    order_detail.total_price_net = prices["total_price_net"]
    order_detail.total_price_with_tax = prices["total_price_with_tax"]


def apply_vies_prices_to_shipping(
    shipping: Shipping,
    source_tax_percentage: float,
    vies_tax_id: int,
) -> None:
    gross = float(shipping.price_tax_incl or 0.0)
    net = _net_from_gross(gross, source_tax_percentage)
    shipping.id_tax = vies_tax_id
    shipping.price_tax_excl = round(net, 2)
    shipping.price_tax_incl = round(net, 2)


def apply_vies_prices_to_shipping_dict(
    shipping_data: Dict[str, Any],
    source_tax_percentage: float,
    vies_tax_id: int,
) -> Dict[str, Any]:
    gross = float(shipping_data.get("price_tax_incl") or 0.0)
    net = _net_from_gross(gross, source_tax_percentage)
    shipping_data["id_tax"] = vies_tax_id
    shipping_data["price_tax_excl"] = round(net, 2)
    shipping_data["price_tax_incl"] = round(net, 2)
    return shipping_data


def apply_vies_exemption_to_order_lines(
    session: Session,
    order_id: int,
    vies_tax_id: int,
    id_country_delivery: Optional[int],
) -> None:
    """Righe ordine non legate a documento: sottrae IVA reale e imposta aliquota VIES."""
    from sqlalchemy import or_

    order_details = (
        session.query(OrderDetail)
        .filter(
            OrderDetail.id_order == order_id,
            or_(
                OrderDetail.id_order_document.is_(None),
                OrderDetail.id_order_document == 0,
            ),
        )
        .all()
    )

    for od in order_details:
        source_pct = resolve_source_tax_percentage(
            session, od.id_tax, id_country_delivery
        )
        apply_vies_prices_to_order_detail(od, source_pct, vies_tax_id)
        session.add(od)


def apply_vies_exemption_to_order_shipping(
    session: Session,
    order: Order,
    vies_tax_id: int,
    id_country_delivery: Optional[int],
) -> None:
    if not order.id_shipping:
        return
    shipping = (
        session.query(Shipping)
        .filter(Shipping.id_shipping == order.id_shipping)
        .first()
    )
    if not shipping:
        return
    source_pct = resolve_source_tax_percentage(
        session, shipping.id_tax, id_country_delivery
    )
    apply_vies_prices_to_shipping(shipping, source_pct, vies_tax_id)
    session.add(shipping)
