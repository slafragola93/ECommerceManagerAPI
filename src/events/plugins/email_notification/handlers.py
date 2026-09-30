"""Invio mail cliente solo al passaggio ordine in Spediti (id_order_state=3)."""

from __future__ import annotations

import logging
from contextlib import contextmanager

from src.database import get_db
from src.events.core.event import Event, EventType
from src.events.interfaces import BaseEventHandler
from src.models.email_template import ORDER_STATE_SHIPPED
from src.services.email.document_mail_service import DocumentMailService

logger = logging.getLogger(__name__)


class EmailNotificationHandler(BaseEventHandler):
    def __init__(self, *, name: str = "email_notification_handler") -> None:
        super().__init__(name=name)

    def can_handle(self, event: Event) -> bool:
        return event.event_type == EventType.ORDER_STATUS_CHANGED.value

    async def handle(self, event: Event) -> None:
        order_id = event.data.get("order_id") or event.data.get("id_order")
        new_state_id = event.data.get("new_state_id")
        if not order_id or new_state_id != ORDER_STATE_SHIPPED:
            return

        try:
            with self._get_db_session() as db:
                result = await DocumentMailService(db).send_order_shipped(int(order_id))
                if result.success:
                    logger.info("Mail Spediti inviata per ordine %s", order_id)
                else:
                    logger.warning(
                        "Mail Spediti non inviata per ordine %s: %s",
                        order_id,
                        result.mail_error_message,
                    )
        except Exception as exc:
            logger.error("Errore mail Spediti ordine %s: %s", order_id, exc, exc_info=True)

    @contextmanager
    def _get_db_session(self):
        db = next(get_db())
        try:
            yield db
        finally:
            db.close()
