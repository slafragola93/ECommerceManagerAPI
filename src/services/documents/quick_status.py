"""Mapping stati rapidi: mail + esito FatturaPA, con overlay notifiche SDI."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

FatturapaStatus = Optional[str]  # null | uploaded | sent | error
MailStatus = Optional[str]  # null | sent | pending | error

_VALID_FATTURAPA = frozenset({"uploaded", "sent", "error"})
_VALID_MAIL = frozenset({"sent", "pending", "error"})


def _truncate(message: Optional[str], max_len: int = 255) -> Optional[str]:
    if not message:
        return None
    text = str(message).strip()
    if not text:
        return None
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def _parse_upload_result(upload_result: Optional[str]) -> Dict[str, Any]:
    if not upload_result:
        return {}
    if isinstance(upload_result, dict):
        return upload_result
    try:
        data = json.loads(upload_result)
        return data if isinstance(data, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {"message": str(upload_result)}


def extract_identificativo_sdi(upload_result: Optional[str]) -> Optional[str]:
    data = _parse_upload_result(upload_result)
    for key in (
        "identificativo_sdi",
        "IdentificativoSdI",
        "sdi_id",
        "sdiId",
        "IdSdi",
        "id_sdi",
    ):
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    nested = data.get("data")
    if isinstance(nested, dict):
        for key in ("identificativo_sdi", "sdi_identificativo", "sdi_id"):
            value = nested.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return None


def map_mail_status(
    mail_status: Optional[str] = None,
    mail_error_message: Optional[str] = None,
) -> Tuple[MailStatus, Optional[str]]:
    status = (mail_status or "").strip().lower() or None
    if status not in _VALID_MAIL:
        return None, None
    error = _truncate(mail_error_message) if status == "error" else None
    return status, error


_SDI_ISSUED = frozenset(
    {"consegnata", "accettata", "rifiutata", "decorrenza_termini", "mancata_consegna"}
)


def map_fiscal_fatturapa_status(
    *,
    is_electronic: bool,
    status: Optional[str],
    upload_result: Optional[str] = None,
    sdi_status: Optional[str] = None,
) -> Tuple[FatturapaStatus, Optional[str], Optional[str]]:
    """
    Deriva esito intermediario / SdI: workflow interno, poi overlay notifiche.

    Returns:
        (fatturapa_status, fatturapa_error_message, identificativo_sdi)
    """
    sdi_id = extract_identificativo_sdi(upload_result)
    if not is_electronic:
        return None, None, sdi_id

    st = (status or "").strip().lower()
    parsed = _parse_upload_result(upload_result)
    raw_msg = parsed.get("message") or parsed.get("error") or parsed.get("Error")
    sdi = (sdi_status or "").strip().lower() or None

    if sdi == "scartata":
        return "error", "Scartata da SDI", sdi_id
    if sdi in _SDI_ISSUED:
        return "sent", None, sdi_id

    if st == "error" or (
        isinstance(parsed.get("status"), str)
        and parsed.get("status", "").lower() == "error"
    ):
        return "error", _truncate(raw_msg) or "Errore FatturaPA", sdi_id

    if st == "uploaded":
        return "uploaded", None, sdi_id
    if st == "sent":
        return "sent", None, sdi_id

    # pending / generated / issued / altro → non ancora su FatturaPA / SdI
    return None, None, sdi_id


def map_purchase_fatturapa_status(
    identificativo_sdi: Optional[str],
) -> Tuple[FatturapaStatus, Optional[str], Optional[str]]:
    """Documento ricevuto via POOL: se ha ID SDI → sent (già transitato)."""
    sdi_id = (identificativo_sdi or "").strip() or None
    if sdi_id:
        return "sent", None, sdi_id
    return None, None, None


def map_ricevuta_fatturapa_status() -> Tuple[FatturapaStatus, Optional[str], Optional[str]]:
    """Ricevute interne: nessun flusso FatturaPA/SDI."""
    return None, None, None


def quick_status_dict(
    *,
    mail_status: Optional[str] = None,
    mail_error_message: Optional[str] = None,
    fatturapa_status: Optional[str] = None,
    fatturapa_error_message: Optional[str] = None,
    identificativo_sdi: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    mail_s, mail_err = map_mail_status(mail_status, mail_error_message)
    fp = (fatturapa_status or None)
    if fp not in _VALID_FATTURAPA:
        fp = None
    fp_err = (
        _truncate(fatturapa_error_message) if fp == "error" else None
    )
    sdi = str(identificativo_sdi).strip() if identificativo_sdi else None
    return {
        "mail_status": mail_s,
        "mail_error_message": mail_err,
        "fatturapa_status": fp,
        "fatturapa_error_message": fp_err,
        "identificativo_sdi": sdi or None,
    }


def fiscal_quick_status_from_doc(doc: Any) -> Dict[str, Optional[str]]:
    fp_status, fp_err, sdi_id = map_fiscal_fatturapa_status(
        is_electronic=bool(getattr(doc, "is_electronic", False)),
        status=getattr(doc, "status", None),
        upload_result=getattr(doc, "upload_result", None),
        sdi_status=getattr(doc, "sdi_status", None),
    )
    persisted_sdi = getattr(doc, "identificativo_sdi", None)
    if persisted_sdi:
        sdi_id = str(persisted_sdi).strip() or sdi_id
    mail_s, mail_err = map_mail_status(
        getattr(doc, "mail_status", None),
        getattr(doc, "mail_error_message", None),
    )
    return quick_status_dict(
        mail_status=mail_s,
        mail_error_message=mail_err,
        fatturapa_status=fp_status,
        fatturapa_error_message=fp_err,
        identificativo_sdi=sdi_id,
    )


def purchase_quick_status_from_invoice(invoice: Any) -> Dict[str, Optional[str]]:
    fp_status, fp_err, sdi_id = map_purchase_fatturapa_status(
        getattr(invoice, "identificativo_sdi", None)
    )
    mail_s, mail_err = map_mail_status(
        getattr(invoice, "mail_status", None),
        getattr(invoice, "mail_error_message", None),
    )
    return quick_status_dict(
        mail_status=mail_s,
        mail_error_message=mail_err,
        fatturapa_status=fp_status,
        fatturapa_error_message=fp_err,
        identificativo_sdi=sdi_id,
    )


def ricevuta_quick_status_from_entity(entity: Any = None) -> Dict[str, Optional[str]]:
    fp_status, fp_err, sdi_id = map_ricevuta_fatturapa_status()
    mail_s, mail_err = map_mail_status(
        getattr(entity, "mail_status", None) if entity is not None else None,
        getattr(entity, "mail_error_message", None) if entity is not None else None,
    )
    return quick_status_dict(
        mail_status=mail_s,
        mail_error_message=mail_err,
        fatturapa_status=fp_status,
        fatturapa_error_message=fp_err,
        identificativo_sdi=sdi_id,
    )
