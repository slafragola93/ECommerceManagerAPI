"""Regole invio / reinvio SDI (ciclo attivo)."""
from __future__ import annotations

import os
from typing import Optional

SDI_API_SEND_DISABLED_DETAIL = (
    "Invio SDI via API disabilitato: l'operatore completa l'invio sul portale "
    "FatturaPA.com dopo aver generato/scaricato l'XML. "
    "Riattivare con FATTURAPA_SDI_API_SEND_ENABLED=true."
)


def is_sdi_api_send_enabled() -> bool:
    """True di default: il gestionale invia via API FatturaPA.com (UploadStop)."""
    raw = os.getenv("FATTURAPA_SDI_API_SEND_ENABLED", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}

SDI_STATUS_SCARTATA = "scartata"
SDI_STATUS_CLOSED = frozenset(
    {
        "consegnata",
        "accettata",
        "rifiutata",
        "decorrenza_termini",
        "mancata_consegna",
    }
)
SENDABLE_WORKFLOW_STATUSES = frozenset({"generated", "uploaded", "error"})


def send_to_sdi_block_reason(doc) -> Optional[str]:
    """Motivo per cui POST .../send-to-sdi non è consentito, o None."""
    sdi_status = getattr(doc, "sdi_status", None)
    status = getattr(doc, "status", None)

    if sdi_status == SDI_STATUS_SCARTATA:
        return (
            "Documento scartato da SDI. Usare POST "
            "/api/v1/fiscal_documents/{id}/retry-send"
        )
    if sdi_status in SDI_STATUS_CLOSED:
        return "Documento già evaso da SDI, reinvio non consentito"
    if status == "sent" and not sdi_status:
        return "Documento già inviato a SDI, in attesa di notifica"
    if status not in SENDABLE_WORKFLOW_STATUSES:
        return f"Invio non consentito nello stato '{status}'"
    return None


def retry_send_block_reason(doc) -> Optional[str]:
    """Motivo per cui POST .../retry-send non è consentito, o None."""
    if not is_sdi_api_send_enabled():
        return SDI_API_SEND_DISABLED_DETAIL
    if not getattr(doc, "is_electronic", False):
        return "Il documento non è elettronico, non può essere reinviato a SDI"
    if getattr(doc, "sdi_status", None) != SDI_STATUS_SCARTATA:
        return "Reinvio consentito solo dopo scarto SDI (NS)"
    return None


def invoice_edit_block_reason(doc) -> Optional[str]:
    """PATCH consentito se pending oppure non ancora evaso dallo SdI (null/scartata)."""
    sdi_status = getattr(doc, "sdi_status", None)
    status = getattr(doc, "status", None)
    if status == "cancelled":
        return "Documento annullato, non modificabile"
    if sdi_status in SDI_STATUS_CLOSED:
        return "Documento già evaso da SDI, modifica non consentita"
    if status in {"pending", "generated", "uploaded", "error", "sent"}:
        return None
    return f"Fattura non aggiornabile nello stato '{status}'"


def reset_xml_block_reason(doc) -> Optional[str]:
    """Azzeramento XML: solo se lo SdI non ha ancora accettato il file."""
    if getattr(doc, "sdi_status", None) in SDI_STATUS_CLOSED:
        return "Documento già evaso da SDI, XML non eliminabile"
    if getattr(doc, "status", None) == "cancelled":
        return "Documento annullato"
    if not getattr(doc, "xml_content", None) and not getattr(doc, "filename", None):
        return "Nessun XML da eliminare"
    return None


def generate_xml_block_reason(
    doc, api_send_enabled: Optional[bool] = None
) -> Optional[str]:
    """Con API send on, dopo NS lo XML si rigenera solo via retry-send."""
    sdi_status = getattr(doc, "sdi_status", None)
    if sdi_status in SDI_STATUS_CLOSED:
        return "Documento già evaso da SDI, generazione XML non consentita"
    if sdi_status != SDI_STATUS_SCARTATA:
        return None
    enabled = (
        is_sdi_api_send_enabled() if api_send_enabled is None else api_send_enabled
    )
    if enabled:
        return (
            "Documento scartato da SDI. Usare POST "
            "/api/v1/fiscal_documents/{id}/retry-send "
            "per assegnare un nuovo ProgressivoInvio e reinviare"
        )
    return None


def api_sdi_send_disabled_reason(send_to_sdi: bool) -> Optional[str]:
    """Blocca UploadStop / retry finché l'invio resta sul portale."""
    if send_to_sdi and not is_sdi_api_send_enabled():
        return SDI_API_SEND_DISABLED_DETAIL
    return None
