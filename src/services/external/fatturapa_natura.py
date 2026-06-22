"""Helper codice natura IVA per FatturaPA (tag Natura)."""
import re
from typing import Optional

# Codici ammessi in Natura: N1–N7 con eventuale sottocodice (es. N3.1, N6.2).
NATURA_CODE_PATTERN = re.compile(r"^N[1-7](?:\.\d+)?$", re.IGNORECASE)


def normalize_natura_code(value: Optional[str]) -> Optional[str]:
    """
    Normalizza il codice natura per il tag XML Natura.

    Il FE persiste in taxes.electronic_code solo il codice breve (es. N3.1).
    La descrizione normativa va in taxes.note → RiferimentoNormativo.
    """
    if value is None:
        return None
    code = str(value).strip().upper()
    if not code:
        return None
    if NATURA_CODE_PATTERN.match(code):
        return code
    return None
