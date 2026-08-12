"""Unit tests for audit EventBus handler."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.events.core.event import Event, EventType
from src.services.audit.audit_log_handler import handle_audit_event


@pytest.mark.asyncio
async def test_handle_audit_event_persists_row():
    event = Event(
        event_type=EventType.ORDER_CREATED.value,
        data={"id_order": 99, "before": None, "after": {"id_order": 99}},
        metadata={
            "actor_id": 7,
            "actor_username": "alice",
            "actor_role": "ORDINI",
            "ip_address": "10.0.0.1",
            "request_id": "req-123",
        },
        timestamp=datetime.now(timezone.utc),
    )

    mock_session = MagicMock()
    with patch(
        "src.services.audit.audit_log_handler.SessionLocal",
        return_value=mock_session,
    ):
        await handle_audit_event(event)

    assert mock_session.add.called
    row = mock_session.add.call_args[0][0]
    assert row.action == "order.create"
    assert row.resource_type == "order"
    assert row.resource_id == "99"
    assert row.actor_id == 7
    assert row.actor_username == "alice"
    assert row.level == "standard"
    assert row.ip_address == "10.0.0.1"
    assert row.request_id == "req-123"
    assert row.status == "success"
    assert row.changes == {"before": None, "after": {"id_order": 99}}
    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_handle_audit_event_db_failure_does_not_raise():
    event = Event(
        event_type=EventType.AUTH_LOGIN_FAILED.value,
        data={"username": "bob", "status": "failure"},
        metadata={"actor_username": "bob", "status": "failure"},
    )

    mock_session = MagicMock()
    mock_session.commit.side_effect = RuntimeError("db down")

    with patch(
        "src.services.audit.audit_log_handler.SessionLocal",
        return_value=mock_session,
    ):
        await handle_audit_event(event)  # must not raise

    mock_session.rollback.assert_called_once()
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_handle_audit_event_ignores_unmapped_type():
    event = Event(
        event_type=EventType.PLUGIN_LOADED.value,
        data={"plugin": "x"},
        metadata={},
    )
    with patch("src.services.audit.audit_log_handler.SessionLocal") as session_factory:
        await handle_audit_event(event)
        session_factory.assert_not_called()
