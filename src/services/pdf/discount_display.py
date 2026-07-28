"""Helper condivisi per visualizzazione sconti nei PDF (fattura/NC, ordine, preventivo).

Regole display colonna sconto:
- se ``reduction_percent > 0`` → percentuale (es. ``12,00 %``)
- altrimenti se importo > 0 → cifra (es. ``500,00``)
- altrimenti ``0,00 %``

Priorità calcolo importo: % > reduction_amount > differenza unit×qty − totale riga.
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple


def resolve_line_discount(
    *,
    qty: float,
    unit_net: float,
    line_net: float,
    reduction_percent: float,
    reduction_amount: float,
) -> Tuple[float, float]:
    """
    Calcola importo sconto riga e % equivalente.

    Returns:
        (discount_amount, display_percent)
    """
    line_base = unit_net * qty if unit_net and qty else 0.0
    discount = 0.0
    display_percent = max(0.0, float(reduction_percent or 0.0))

    if display_percent > 0 and line_base > 0:
        discount = line_base * (display_percent / 100.0)
    elif reduction_amount and float(reduction_amount) > 0:
        discount = float(reduction_amount)
        if line_base > 0:
            display_percent = (discount / line_base) * 100.0
    elif line_base > 0 and line_net >= 0:
        derived = line_base - float(line_net)
        if derived > 1e-6:
            discount = derived
            display_percent = (discount / line_base) * 100.0

    return max(0.0, discount), display_percent


def format_discount_label(
    *,
    reduction_percent: float,
    discount_amount: float,
    fmt_num: Callable[[Optional[float], int], str],
    fmt_pct: Callable[[Optional[float]], str],
) -> str:
    """Etichetta cella sconto: % se percentuale, cifra se importo."""
    if float(reduction_percent or 0) > 0:
        return fmt_pct(reduction_percent)
    if float(discount_amount or 0) > 0:
        return fmt_num(discount_amount, 2)
    return fmt_pct(0)
