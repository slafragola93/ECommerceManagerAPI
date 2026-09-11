"""Parser notifiche SDI (ciclo attivo): RC, MC, NS, NE, DT/AT."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional
from xml.etree import ElementTree as ET

from src.services.external.fatturapa_filename import local_tag

NOTIFICATION_TYPES = frozenset({"RC", "MC", "NS", "NE", "DT"})
TYPE_ALIASES = {"AT": "DT"}

ROOT_TO_TYPE = {
    "RicevutaConsegna": "RC",
    "MancataConsegna": "MC",
    "NotificaScarto": "NS",
    "NotificaEsito": "NE",
    "NotificaEsitoCommittente": "NE",
    "NotificaDecorrenzaTermini": "DT",
}

FILENAME_TYPE_RE = re.compile(
    r"_(RC|NS|MC|NE|DT|AT)(?:_\d+)?\.xml$",
    re.IGNORECASE,
)
PROGRESSIVO_FROM_FILE_RE = re.compile(
    r"^[A-Z]{2}[A-Z0-9]+_([A-Za-z0-9]+)(?:_[A-Z]{2}(?:_\d+)?)?\.xml$",
    re.IGNORECASE,
)

SDI_STATUS_BY_TYPE = {
    "RC": "consegnata",
    "NS": "scartata",
    "MC": "mancata_consegna",
    "DT": "decorrenza_termini",
}


def _text(element: Optional[ET.Element]) -> Optional[str]:
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    return value or None


def _find_desc(root: ET.Element, name: str) -> Optional[ET.Element]:
    for element in root.iter():
        if local_tag(element) == name:
            return element
    return None


def normalize_notification_type(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    code = str(raw).strip().upper()
    code = TYPE_ALIASES.get(code, code)
    return code if code in NOTIFICATION_TYPES else None


def extract_progressivo_from_filename(nome_file: Optional[str]) -> Optional[str]:
    if not nome_file:
        return None
    name = str(nome_file).strip().split("/")[-1]
    match = PROGRESSIVO_FROM_FILE_RE.match(name)
    return match.group(1) if match else None


def extract_type_from_filename(nome_file: Optional[str]) -> Optional[str]:
    if not nome_file:
        return None
    match = FILENAME_TYPE_RE.search(str(nome_file).strip())
    if not match:
        return None
    return normalize_notification_type(match.group(1))


def resolve_sdi_status(notification_type: str, esito: Optional[str] = None) -> str:
    code = normalize_notification_type(notification_type) or notification_type
    if code == "NE":
        outcome = (esito or "").strip().upper()
        if outcome == "EC02":
            return "rifiutata"
        return "accettata"
    return SDI_STATUS_BY_TYPE.get(code, "inviata")


def is_sdi_notification_entry(entry: Dict[str, Any]) -> bool:
    direzione = (entry.get("Direzione") or "").strip().lower()
    if direzione == "acquisto":
        return False
    tipo = (entry.get("Tipo") or "").strip().lower()
    nome = entry.get("NomeFile") or ""
    if extract_type_from_filename(nome):
        return True
    return tipo in {
        "notifica",
        "ricevuta",
        "notificaesito",
        "ricevutaconsegna",
        "notificascarto",
        "mancataconsegna",
        "decorrenzatermini",
    }


def parse_sdi_notification(
    xml_content: Optional[str],
    *,
    nome_file: Optional[str] = None,
    identificativo_sdi: Optional[str] = None,
) -> Dict[str, Any]:
    notification_type = extract_type_from_filename(nome_file)
    sdi_id = (identificativo_sdi or "").strip() or None
    message = None
    esito = None
    notified_at = None

    if xml_content and xml_content.strip():
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            root = None
        if root is not None:
            root_type = ROOT_TO_TYPE.get(local_tag(root))
            if root_type:
                notification_type = root_type
            sdi_id = sdi_id or _text(_find_desc(root, "IdentificativoSdI"))
            nome_file = nome_file or _text(_find_desc(root, "NomeFile"))
            esito = _text(_find_desc(root, "Esito"))
            descr = _text(_find_desc(root, "Descrizione"))
            lista_err = _text(_find_desc(root, "Errore"))
            message = descr or lista_err
            raw_dt = _text(_find_desc(root, "DataOraRicezione")) or _text(
                _find_desc(root, "DataOraConsegna")
            )
            if raw_dt:
                try:
                    notified_at = datetime.fromisoformat(raw_dt.replace("Z", "+00:00"))
                except ValueError:
                    notified_at = None

    notification_type = normalize_notification_type(notification_type)
    return {
        "notification_type": notification_type,
        "identificativo_sdi": sdi_id,
        "nome_file": nome_file,
        "progressivo_invio": extract_progressivo_from_filename(nome_file),
        "esito": esito,
        "message": message,
        "notified_at": notified_at,
        "sdi_status": resolve_sdi_status(notification_type or "", esito)
        if notification_type
        else None,
    }
