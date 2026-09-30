from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.events.core.event import Event, EventType
from src.events.plugins.email_notification.handlers import EmailNotificationHandler
from src.models.email_template import ORDER_STATE_SHIPPED
from src.schemas.email_template_schema import EmailSendResultSchema


@pytest.mark.asyncio
async def test_handler_ignores_non_shipped_state():
    handler = EmailNotificationHandler()
    event = Event(
        event_type=EventType.ORDER_STATUS_CHANGED.value,
        data={"order_id": 10, "new_state_id": 1},
        metadata={},
    )
    with patch(
        "src.events.plugins.email_notification.handlers.DocumentMailService"
    ) as mocked:
        await handler.handle(event)
        mocked.assert_not_called()


@pytest.mark.asyncio
async def test_handler_sends_when_shipped():
    handler = EmailNotificationHandler()
    event = Event(
        event_type=EventType.ORDER_STATUS_CHANGED.value,
        data={"order_id": 10, "new_state_id": ORDER_STATE_SHIPPED},
        metadata={},
    )
    service = MagicMock()
    service.send_order_shipped = AsyncMock(
        return_value=EmailSendResultSchema(success=True, mail_status="sent")
    )
    session = MagicMock()
    with patch.object(handler, "_get_db_session") as ctx:
        ctx.return_value.__enter__.return_value = session
        ctx.return_value.__exit__.return_value = False
        with patch(
            "src.events.plugins.email_notification.handlers.DocumentMailService",
            return_value=service,
        ):
            await handler.handle(event)
    service.send_order_shipped.assert_awaited_once_with(10)
