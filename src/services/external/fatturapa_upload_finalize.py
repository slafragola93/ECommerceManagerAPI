"""Finalize upload FatturaPA.com (singolo e bulk send-to-sdi)."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from src.events.core.event import Event, EventType
from src.events.runtime import emit_event
from src.models.fiscal_document import FiscalDocument

logger = logging.getLogger(__name__)


class FatturaPAUploadError(Exception):
    """Upload Stop fallito: status documento già aggiornato a ``error``."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def finalize_fatturapa_upload(
    repo,
    id_fiscal_document: int,
    stop_result: Dict[str, Any],
    send_to_sdi: bool,
) -> FiscalDocument:
    """
    Aggiorna status dopo UploadStop / UploadStop1.

    Raises:
        FatturaPAUploadError: se stop_result indica errore (status già = error).
    """
    if stop_result.get("status") == "error":
        repo.update_fiscal_document_status(
            id_fiscal_document=id_fiscal_document,
            status="error",
            upload_result=json.dumps(stop_result) if stop_result else None,
        )
        raise FatturaPAUploadError(
            stop_result.get("message", "Upload Stop fallito")
        )

    final_status = "sent" if send_to_sdi else "uploaded"
    doc = repo.update_fiscal_document_status(
        id_fiscal_document=id_fiscal_document,
        status=final_status,
        upload_result=json.dumps(stop_result) if stop_result else None,
    )

    if send_to_sdi and doc:
        try:
            emit_event(
                Event(
                    event_type=EventType.FISCAL_DOCUMENT_SENT_TO_SDI.value,
                    data={
                        "id_fiscal_document": id_fiscal_document,
                        "status": final_status,
                    },
                    metadata={},
                )
            )
        except Exception as e:
            logger.warning(
                "Failed to emit FISCAL_DOCUMENT_SENT_TO_SDI for %s: %s",
                id_fiscal_document,
                e,
                exc_info=True,
            )

    return doc
