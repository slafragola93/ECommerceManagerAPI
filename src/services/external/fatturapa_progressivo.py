"""ProgressivoInvio SDI: serie unica, max 10 caratteri (XSD String10Type)."""
from __future__ import annotations

from typing import Iterable, Optional

PROGRESSIVO_MAX_LEN = 10
PROGRESSIVO_PAD = 6


def format_progressivo_invio(number: int) -> str:
    if number < 1:
        raise ValueError("ProgressivoInvio deve essere >= 1")
    formatted = str(number).zfill(PROGRESSIVO_PAD)
    if len(formatted) > PROGRESSIVO_MAX_LEN:
        raise ValueError("ProgressivoInvio supera 10 caratteri")
    return formatted


def parse_progressivo_invio(raw: object) -> Optional[int]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or not text.isdigit():
        return None
    return int(text)


def next_progressivo_from_values(values: Iterable[object]) -> str:
    max_num = 0
    for raw in values:
        parsed = parse_progressivo_invio(raw)
        if parsed is not None:
            max_num = max(max_num, parsed)
    return format_progressivo_invio(max_num + 1)
