"""Risoluzione aliquota/natura IVA per righe XML FatturaPA (incluso VIES N3.2)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

from src.models.tax import Tax
from src.services.external.fatturapa_natura import normalize_natura_code
from src.vies.tax_resolution import is_vies_eligible_status

VIES_NATURA_CODE = "N3.2"
VIES_DEFAULT_NORMATIVO = (
    "Non imponibili - cessioni intracomunitarie (art. 41 DL 331/93)"
)

RiepilogoKey = Tuple[str, Optional[str]]


@dataclass(frozen=True)
class FatturaPALineTax:
    """Aliquota e natura per una riga DettaglioLinee / blocco DatiRiepilogo."""

    aliquota: Decimal
    natura: Optional[str]
    riferimento_normativo: Optional[str]


def _decimal(value: Any, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


def resolve_line_tax(
    tax: Optional[Tax],
    *,
    vies_eligible: bool,
    is_product_line: bool = True,
) -> FatturaPALineTax:
    """
    Risolve AliquotaIVA, Natura e RiferimentoNormativo per una riga.

    - Righe prodotto con ordine VIES eligible → 0% + N3.2 (art. 41 DL 331/93).
    - Spedizione → usa l'aliquota effettiva del tax spedizione (può restare 22%).
    - Aliquota 0% non VIES → natura da Tax.electronic_code.
    """
    if tax is not None and tax.percentage is not None:
        aliquota = _decimal(tax.percentage)
    else:
        aliquota = Decimal("22")

    natura = normalize_natura_code(tax.electronic_code if tax else None)
    note = ((tax.note or "").strip() or None) if tax else None

    if vies_eligible and is_product_line:
        aliquota = Decimal("0")
        natura = natura or VIES_NATURA_CODE
        note = note or VIES_DEFAULT_NORMATIVO
    elif aliquota == 0:
        if not natura and vies_eligible and is_product_line:
            natura = VIES_NATURA_CODE
            note = note or VIES_DEFAULT_NORMATIVO

    return FatturaPALineTax(
        aliquota=aliquota,
        natura=natura if aliquota == 0 else None,
        riferimento_normativo=note if aliquota == 0 else None,
    )


def compute_line_net_total(line: Dict[str, Any]) -> Decimal:
    """PrezzoTotale netto IVA per riga (quantità × prezzo − sconti)."""
    qty = _decimal(line.get("product_qty"), "1")
    unit = _decimal(line.get("product_price"), "0")
    base = unit * qty

    reduction_percent = _decimal(line.get("reduction_percent"), "0")
    reduction_amount = _decimal(line.get("reduction_amount"), "0")

    if reduction_percent != 0:
        net = base - base * (reduction_percent / Decimal("100"))
    elif reduction_amount != 0:
        net = base - reduction_amount
    else:
        net = base

    return net.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def enrich_line_item_tax_fields(
    line: Dict[str, Any],
    line_tax: FatturaPALineTax,
) -> Dict[str, Any]:
    """Aggiunge campi tax_* usati da validator e _generate_xml."""
    enriched = dict(line)
    enriched["tax_percentage"] = float(line_tax.aliquota)
    enriched["tax_nature"] = line_tax.natura
    enriched["tax_note"] = line_tax.riferimento_normativo
    enriched["line_net_total"] = float(compute_line_net_total(line))
    return enriched


def build_riepilogo_groups(
    lines: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Raggruppa righe per (AliquotaIVA, Natura) → blocchi DatiRiepilogo.

    Ogni voce in `lines` deve avere: line_net_total, tax_percentage, tax_nature, tax_note.
    """
    buckets: Dict[RiepilogoKey, Dict[str, Any]] = {}

    for line in lines:
        net = _decimal(line.get("line_net_total"), "0")
        if net == 0:
            continue

        rate = _decimal(line.get("tax_percentage"), "0")
        natura = line.get("tax_nature")
        key: RiepilogoKey = (f"{rate:.2f}", natura)

        if key not in buckets:
            buckets[key] = {
                "AliquotaIVA": float(rate),
                "Natura": natura,
                "RiferimentoNormativo": line.get("tax_note"),
                "ImponibileImporto": Decimal("0"),
                "Imposta": Decimal("0"),
            }

        imposta = Decimal("0") if rate == 0 else (net * rate / Decimal("100"))
        imposta = imposta.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        buckets[key]["ImponibileImporto"] += net
        buckets[key]["Imposta"] += imposta

        if not buckets[key]["RiferimentoNormativo"] and line.get("tax_note"):
            buckets[key]["RiferimentoNormativo"] = line.get("tax_note")

    result: List[Dict[str, Any]] = []
    for group in buckets.values():
        group["ImponibileImporto"] = float(
            group["ImponibileImporto"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )
        group["Imposta"] = float(
            group["Imposta"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )
        result.append(group)

    result.sort(key=lambda g: (g["AliquotaIVA"], g.get("Natura") or ""))
    return result


def vies_eligible_from_order_data(order_data: Dict[str, Any]) -> bool:
    return is_vies_eligible_status(order_data.get("vies_status"))
