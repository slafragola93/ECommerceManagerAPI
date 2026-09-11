"""Gate PEC prima dell'invio SDI (send_to_sdi=true).

XXXXXXX senza PECDestinatario → blocco (estero / codice ignoto).
0000000 senza PEC → consentito (B2C, cassetto fiscale / area riservata).
"""
from __future__ import annotations

import re
from typing import Optional, Tuple
from xml.etree import ElementTree as ET

from src.services.external.fatturapa_filename import local_tag

CODICE_ESTERO = "XXXXXXX"
PEC_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def extract_sdi_recapito(xml_content: str) -> Tuple[str, str]:
    """Ritorna (CodiceDestinatario, PECDestinatario) dall'XML già generato."""
    if not xml_content or not str(xml_content).strip():
        return "", ""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return "", ""

    codice = ""
    pec = ""
    for element in root.iter():
        tag = local_tag(element)
        text = (element.text or "").strip()
        if tag == "CodiceDestinatario" and text:
            codice = text
        elif tag == "PECDestinatario" and text:
            pec = text
    return codice, pec


def pec_gate_error(xml_content: str) -> Optional[dict]:
    """None se l'invio SDI è consentito; altrimenti dict field/message/rule."""
    codice, pec = extract_sdi_recapito(xml_content)
    if pec and not PEC_EMAIL_RE.match(pec):
        return {
            "field": "PECDestinatario",
            "message": f"PECDestinatario non valida: '{pec}'",
            "rule": "pec_gate_formato",
            "value": pec,
        }
    if codice == CODICE_ESTERO and not pec:
        return {
            "field": "PECDestinatario",
            "message": (
                "Invio SDI bloccato: PECDestinatario è obbligatorio "
                "quando CodiceDestinatario è XXXXXXX"
            ),
            "rule": "pec_gate",
            "value": None,
        }
    return None
