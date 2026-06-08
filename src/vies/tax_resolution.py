"""
Aliquote VIES e fallback globale.

- `resolve_vies_exemption_tax_id_*` / `is_vies_eligible_status`: esenzione manuale e POST ordine con
  `vies_status=eligible` esplicito (non usare in sync PrestaShop).
- `resolve_tax_id_for_delivery`: default paese/globale per futuri flussi app (non sync).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.models.order import ViesStatus
from src.models.tax import Tax
from src.repository.tax_repository import TaxRepository
from src.vies.vies_app_configuration import get_reverse_charge_id_tax


def is_vies_eligible_status(vies_status: Optional[ViesStatus | str]) -> bool:
    """True solo se lo stato ordine è esplicitamente eligible (creazione/rettifica VIES)."""
    if vies_status is None:
        return False
    if isinstance(vies_status, ViesStatus):
        return vies_status == ViesStatus.ELIGIBLE
    return str(vies_status).lower() == ViesStatus.ELIGIBLE.value


def get_vies_exemption_tax_id(session: Session) -> Optional[int]:
    """
    id_tax per esenzione VIES: reverse_charge da settings se configurato e valido.
    Il chiamante applica fallback (es. prima tax 0%) se None.
    """
    reverse_id = get_reverse_charge_id_tax(session)
    if not reverse_id:
        return None
    if TaxRepository(session).get_tax_by_id(reverse_id):
        return reverse_id
    return None


def resolve_vies_exemption_tax_id_with_fallback(session: Session) -> int:
    """
    id_tax per esenzione VIES / creazione eligible: reverse_charge, else prima tax 0%, else crea IVA 0% VIES.
    """
    configured = get_vies_exemption_tax_id(session)
    if configured:
        return configured
    tax = (
        session.query(Tax)
        .filter(Tax.percentage == 0)
        .order_by(Tax.id_tax)
        .first()
    )
    if tax:
        return tax.id_tax
    tax = Tax(
        name="IVA 0% VIES",
        percentage=0,
        code="VAT0",
        is_default=0,
        electronic_code="",
        note="Aliquota esenzione VIES intra-UE B2B",
    )
    session.add(tax)
    session.flush()
    return tax.id_tax


def resolve_tax_id_for_delivery(
    session: Session,
    id_country_delivery: Optional[int],
    vies_status: Optional[ViesStatus | str],
) -> Optional[int]:
    """
    Algoritmo prodotto:
    - eligible → settings.reverse_charge_id_tax
    - elif default paese (id_country, is_default=1)
    - elif default globale (id_country IS NULL, is_default=1)
    - else None
    """
    repo = TaxRepository(session)

    status_value = (
        vies_status.value
        if isinstance(vies_status, ViesStatus)
        else (str(vies_status).lower() if vies_status is not None else None)
    )

    if status_value == ViesStatus.ELIGIBLE.value:
        reverse_id = get_reverse_charge_id_tax(session)
        if reverse_id:
            return reverse_id
        return None

    if id_country_delivery and id_country_delivery > 0:
        country_tax = repo.get_default_by_country(id_country_delivery)
        if country_tax:
            return country_tax.id_tax

    global_tax = repo.get_global_default()
    if global_tax:
        return global_tax.id_tax

    return None
