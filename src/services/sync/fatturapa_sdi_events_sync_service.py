"""Polling notifiche SDI ciclo attivo (Pool Vendita). Non modifica il sync acquisti."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.repository.app_configuration_repository import AppConfigurationRepository
from src.repository.fiscal_document_sdi_notification_repository import (
    FiscalDocumentSdiNotificationRepository,
)
from src.services.external.fatturapa_sdi_notification_parser import (
    is_sdi_notification_entry,
    parse_sdi_notification,
)
from src.services.sync.fatturapa_pool_sync_service import FatturaPAPoolSyncService

logger = logging.getLogger(__name__)


class FatturaPASdiEventsSyncService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = FiscalDocumentSdiNotificationRepository(db)
        self._pool = FatturaPAPoolSyncService(db)

    async def sync_events(self) -> Dict[str, Any]:
        stats = {
            "start_time": datetime.now().isoformat(),
            "status": "success",
            "entries_found": 0,
            "entries_processed": 0,
            "entries_saved": 0,
            "entries_skipped": 0,
            "errors": [],
        }
        try:
            pool_data = await self._pool._get_pool_data()
            if not pool_data or "Complete" not in pool_data:
                stats["status"] = "warning"
                stats["errors"].append("POOL Complete URL mancante")
                return stats

            feed_xml = await self._pool._download_feed(pool_data["Complete"])
            entries = self._pool._parse_feed(feed_xml or "")
            stats["entries_found"] = len(entries)

            for entry in entries:
                try:
                    if not is_sdi_notification_entry(entry):
                        stats["entries_skipped"] += 1
                        continue
                    stats["entries_processed"] += 1
                    xml_content, _path = await self._pool._download_file(entry)
                    result = self.persist_notification(
                        xml_content=xml_content,
                        nome_file=entry.get("NomeFile"),
                        identificativo_sdi=entry.get("IdentificativoSdI"),
                    )
                    if result == "saved":
                        stats["entries_saved"] += 1
                    else:
                        stats["entries_skipped"] += 1
                except Exception as exc:
                    stats["errors"].append(str(exc))
                    logger.exception("Errore processamento notifica SDI")

            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            stats["status"] = "error"
            stats["errors"].append(str(exc))
            logger.exception("Errore sync eventi SDI")
        stats["end_time"] = datetime.now().isoformat()
        return stats

    def persist_notification(
        self,
        *,
        xml_content: Optional[str],
        nome_file: Optional[str],
        identificativo_sdi: Optional[str] = None,
    ) -> str:
        parsed = parse_sdi_notification(
            xml_content,
            nome_file=nome_file,
            identificativo_sdi=identificativo_sdi,
        )
        if not parsed.get("notification_type"):
            return "skipped"

        progressivo = parsed.get("progressivo_invio")
        doc = (
            self.repo.find_document_by_progressivo(progressivo)
            if progressivo
            else None
        )
        if not doc:
            return "skipped"

        if self.repo.exists(
            doc.id_fiscal_document,
            parsed["notification_type"],
            parsed.get("nome_file"),
        ):
            return "skipped"

        self.repo.create(
            id_fiscal_document=doc.id_fiscal_document,
            notification_type=parsed["notification_type"],
            identificativo_sdi=parsed.get("identificativo_sdi"),
            nome_file=parsed.get("nome_file"),
            message=parsed.get("message"),
            payload=xml_content,
            notified_at=parsed.get("notified_at"),
        )
        self.repo.update_document_sdi(
            doc,
            sdi_status=parsed.get("sdi_status"),
            identificativo_sdi=parsed.get("identificativo_sdi"),
        )
        return "saved"


def get_sdi_sync_service(db: Session) -> FatturaPASdiEventsSyncService:
    return FatturaPASdiEventsSyncService(db)


async def sync_fatturapa_sdi_events_periodic():
    from src.database import SessionLocal

    db = SessionLocal()
    try:
        config = AppConfigurationRepository(db)
        if not config.get_by_name_and_category("api_key", "fatturapa"):
            logger.warning("Sync SDI events saltato: API key mancante")
            return {"status": "skipped", "errors": ["API key mancante"]}
        return await FatturaPASdiEventsSyncService(db).sync_events()
    except ValueError as exc:
        logger.warning("Sync SDI events saltato: %s", exc)
        return {"status": "skipped", "errors": [str(exc)]}
    except Exception as exc:
        logger.error("Errore sync SDI events: %s", exc, exc_info=True)
        return {"status": "error", "errors": [str(exc)]}
    finally:
        db.close()


async def run_fatturapa_sdi_events_sync_task(_db: Session = None):
    import asyncio

    interval = int(os.getenv("FATTURAPA_SDI_EVENTS_SYNC_INTERVAL_SECONDS", "300"))
    initial_delay = int(
        os.getenv("FATTURAPA_SDI_EVENTS_SYNC_INITIAL_DELAY_SECONDS", "60")
    )
    logger.info(
        "Starting FatturaPA SDI events sync (delay=%ss, interval=%ss)",
        initial_delay,
        interval,
    )
    try:
        await asyncio.sleep(max(0, initial_delay))
        await sync_fatturapa_sdi_events_periodic()
    except Exception as exc:
        logger.error("Errore primo sync SDI events: %s", exc, exc_info=True)

    while True:
        try:
            await asyncio.sleep(max(60, interval))
            await sync_fatturapa_sdi_events_periodic()
        except Exception as exc:
            logger.error("Errore loop sync SDI events: %s", exc, exc_info=True)
