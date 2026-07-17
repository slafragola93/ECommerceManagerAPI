"""
Risoluzione aliquota IVA spedizione per paese di consegna e ricalcolo imponibile.

Allineato alla logica righe prodotto (default paese → globale → fallback).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.models.address import Address
from src.models.order import Order
from src.repository.tax_repository import TaxRepository
from src.services.core.tool import calculate_price_with_tax, calculate_price_without_tax


def get_delivery_country_id(
    session: Session,
    *,
    id_country: Optional[int] = None,
    id_address_delivery: Optional[int] = None,
) -> Optional[int]:
    if id_country is not None and id_country > 0:
        return id_country
    if not id_address_delivery:
        return None
    address = (
        session.query(Address)
        .filter(Address.id_address == id_address_delivery)
        .first()
    )
    if address and address.id_country and address.id_country > 0:
        return address.id_country
    return None


def resolve_shipping_tax_info(
    session: Session,
    *,
    id_country_delivery: Optional[int],
    vies_status: Optional[Any] = None,
) -> Dict[str, float | int]:
    """Restituisce id_tax e percentage per spedizione (VIES → esenzione, altrimenti default paese)."""
    from src.vies.tax_resolution import (
        is_vies_eligible_status,
        resolve_vies_exemption_tax_id_with_fallback,
    )

    if is_vies_eligible_status(vies_status):
        return {
            "id_tax": resolve_vies_exemption_tax_id_with_fallback(session),
            "percentage": 0.0,
        }

    repo = TaxRepository(session)
    if id_country_delivery and id_country_delivery > 0:
        info = repo.get_tax_info_by_country(id_country_delivery)
        if info:
            return info

    global_default = repo.get_global_default()
    if global_default is not None and global_default.percentage is not None:
        return {
            "id_tax": global_default.id_tax,
            "percentage": float(global_default.percentage),
        }

    default_pct = repo.get_default_tax_percentage_from_app_config(22.0)
    return {"id_tax": 1, "percentage": default_pct}


def apply_delivery_tax_to_shipping_data(
    session: Session,
    shipping_data: dict,
    *,
    id_country_delivery: Optional[int] = None,
    id_address_delivery: Optional[int] = None,
    vies_status: Optional[Any] = None,
    gross_is_source: bool = True,
) -> None:
    """
    Imposta id_tax dal paese di consegna e ricalcola price_tax_excl o price_tax_incl mancante.

    Con gross_is_source=True (default, sync e-commerce): price_tax_incl è la fonte, ricalcola excl.
    """
    from src.vies.exemption_calculation import (
        apply_vies_prices_to_shipping_dict,
        resolve_source_tax_percentage,
    )
    from src.vies.tax_resolution import is_vies_eligible_status

    country_id = id_country_delivery
    if country_id is None:
        country_id = get_delivery_country_id(
            session, id_address_delivery=id_address_delivery
        )

    incl = float(shipping_data.get("price_tax_incl") or 0)
    excl_raw = shipping_data.get("price_tax_excl")
    excl = float(excl_raw) if excl_raw is not None else None

    if is_vies_eligible_status(vies_status) and incl > 0:
        from src.vies.tax_resolution import resolve_vies_exemption_tax_id_with_fallback

        vies_tax_id = resolve_vies_exemption_tax_id_with_fallback(session)
        source_pct = resolve_source_tax_percentage(
            session, shipping_data.get("id_tax"), country_id
        )
        apply_vies_prices_to_shipping_dict(shipping_data, source_pct, vies_tax_id)
        return

    tax_info = resolve_shipping_tax_info(
        session, id_country_delivery=country_id, vies_status=vies_status
    )
    shipping_data["id_tax"] = int(tax_info["id_tax"])
    pct = float(tax_info["percentage"])

    if incl > 0 and gross_is_source:
        shipping_data["price_tax_excl"] = round(
            calculate_price_without_tax(incl, pct), 2
        )
    elif excl is not None and excl > 0 and incl == 0:
        shipping_data["price_tax_incl"] = round(
            calculate_price_with_tax(excl, pct, quantity=1), 2
        )


def apply_delivery_tax_to_shipping(
    session: Session,
    shipping: Any,
    order: Optional[Order] = None,
    *,
    vies_status: Optional[Any] = None,
    gross_is_source: bool = True,
) -> None:
    """Applica aliquota paese consegna su modello Shipping (update in-place)."""
    country_id: Optional[int] = None
    vies = vies_status
    if order is not None:
        from src.vies.exemption_calculation import get_order_delivery_country_id

        country_id = get_order_delivery_country_id(session, order)
        if vies is None:
            vies = order.vies_status

    data = {
        "id_tax": shipping.id_tax,
        "price_tax_incl": shipping.price_tax_incl,
        "price_tax_excl": shipping.price_tax_excl,
    }
    apply_delivery_tax_to_shipping_data(
        session,
        data,
        id_country_delivery=country_id,
        vies_status=vies,
        gross_is_source=gross_is_source,
    )
    shipping.id_tax = data["id_tax"]
    shipping.price_tax_incl = data["price_tax_incl"]
    shipping.price_tax_excl = data["price_tax_excl"]
