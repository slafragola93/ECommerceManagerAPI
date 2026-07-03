"""
Persistenza prezzi riga ordine — BE-1 bridge.

Se il payload contiene tutti i campi prezzo + id_tax, i valori vengono salvati così come
ricevuti (solo arrotondamento). Altrimenti si applica il calcolo legacy BE.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Union

from sqlalchemy.orm import Session

from src.models.tax import Tax
from src.services.core.tool import (
    calculate_amount_with_percentage,
    calculate_price_with_tax,
    calculate_price_without_tax,
)

PRICE_FIELD_NAMES = (
    "unit_price_net",
    "unit_price_with_tax",
    "total_price_net",
    "total_price_with_tax",
)


def _get_field(data: Union[Mapping[str, Any], Any], name: str) -> Any:
    if isinstance(data, Mapping):
        return data.get(name)
    return getattr(data, name, None)


def round_price_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), 2)


def has_complete_price_payload(data: Union[Mapping[str, Any], Any]) -> bool:
    """True se id_tax e tutti e 4 i campi prezzo sono valorizzati."""
    id_tax = _get_field(data, "id_tax")
    if id_tax is None or int(id_tax) <= 0:
        return False
    for field in PRICE_FIELD_NAMES:
        if _get_field(data, field) is None:
            return False
    return True


def has_complete_price_update_payload(update_data: Mapping[str, Any]) -> bool:
    """Per PUT parziale: tutti i campi prezzo devono essere esplicitamente nel body."""
    required = ("id_tax", *PRICE_FIELD_NAMES)
    return all(key in update_data for key in required) and int(update_data["id_tax"]) > 0


def persisted_price_fields(data: Union[Mapping[str, Any], Any]) -> Dict[str, float]:
    return {field: round_price_value(_get_field(data, field)) for field in PRICE_FIELD_NAMES}


def calculate_price_fields_legacy(
    *,
    id_tax: Optional[int],
    unit_price_net: Optional[float],
    unit_price_with_tax: Optional[float],
    product_qty: int,
    reduction_percent: float = 0.0,
    reduction_amount: float = 0.0,
    db: Session,
) -> Dict[str, float]:
    """Calcolo IVA legacy (comportamento pre-bridge)."""
    quantity = product_qty or 1
    tax_percentage = 0.0
    if id_tax:
        tax = db.query(Tax).filter(Tax.id_tax == id_tax).first()
        if tax and tax.percentage is not None:
            tax_percentage = float(tax.percentage)

    unit_net = unit_price_net
    unit_gross = unit_price_with_tax

    if (
        unit_gross is not None
        and unit_gross > 0
        and (unit_net is None or unit_net == 0)
    ):
        unit_net = calculate_price_without_tax(unit_gross, tax_percentage)

    if (
        unit_net is not None
        and unit_net > 0
        and (unit_gross is None or unit_gross == 0)
    ):
        unit_gross = calculate_price_with_tax(unit_net, tax_percentage, quantity=1)

    total_base_net = (unit_net or 0.0) * quantity
    total_base_with_tax = (unit_gross or 0.0) * quantity

    if reduction_percent > 0:
        discount = calculate_amount_with_percentage(total_base_net, reduction_percent)
        total_price_net = total_base_net - discount
    elif reduction_amount > 0:
        total_price_net = total_base_net - reduction_amount
    else:
        total_price_net = total_base_net

    if total_price_net > 0 and tax_percentage > 0:
        total_price_with_tax = calculate_price_with_tax(
            total_price_net, tax_percentage, quantity=1
        )
    else:
        total_price_with_tax = total_base_with_tax

    return {
        "unit_price_net": round_price_value(unit_net) or 0.0,
        "unit_price_with_tax": round_price_value(unit_gross) or 0.0,
        "total_price_net": round_price_value(total_price_net) or 0.0,
        "total_price_with_tax": round_price_value(total_price_with_tax) or 0.0,
    }


def resolve_price_fields(
    data: Union[Mapping[str, Any], Any],
    db: Session,
    *,
    product_qty: Optional[int] = None,
    reduction_percent: Optional[float] = None,
    reduction_amount: Optional[float] = None,
) -> Dict[str, float]:
    """
    Restituisce i 4 campi prezzo: persist-only se payload completo, altrimenti legacy.
    """
    if has_complete_price_payload(data):
        return persisted_price_fields(data)

    qty = product_qty if product_qty is not None else _get_field(data, "product_qty") or 1
    rp = reduction_percent if reduction_percent is not None else _get_field(data, "reduction_percent") or 0.0
    ra = reduction_amount if reduction_amount is not None else _get_field(data, "reduction_amount") or 0.0

    return calculate_price_fields_legacy(
        id_tax=_get_field(data, "id_tax"),
        unit_price_net=_get_field(data, "unit_price_net"),
        unit_price_with_tax=_get_field(data, "unit_price_with_tax"),
        product_qty=int(qty),
        reduction_percent=float(rp or 0.0),
        reduction_amount=float(ra or 0.0),
        db=db,
    )
