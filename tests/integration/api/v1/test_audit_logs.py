"""Integration tests for GET /api/v1/audit-logs."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.events.core.event import Event, EventType
from src.services.audit import register_audit_handlers
from src.services.routers.auth_service import get_current_user
from tests.conftest import EventBusSpy
from tests.factories.audit_log import create_audit_log


def _full_crud_user() -> dict:
    return {
        "username": "admin",
        "id": 1,
        "role": "ADMIN",
        "role_type": "full_crud",
    }


def _custom_user_no_audit() -> dict:
    return {
        "username": "limited",
        "id": 99,
        "role": "USER",
        "role_type": "custom",
    }


@pytest.fixture
def audit_admin_client(test_app) -> TestClient:
    test_app.dependency_overrides[get_current_user] = _full_crud_user
    return TestClient(test_app)


@pytest.fixture
def audit_denied_client(test_app, db_session) -> TestClient:
    """Utente custom senza modulo audit → 403."""
    test_app.dependency_overrides[get_current_user] = _custom_user_no_audit
    return TestClient(test_app)


@pytest.mark.asyncio
async def test_order_created_event_writes_audit_row(
    db_session, event_bus_spy: EventBusSpy
):
    await register_audit_handlers(event_bus_spy)

    with patch(
        "src.services.audit.audit_log_handler.SessionLocal",
        return_value=db_session,
    ), patch.object(db_session, "close"):
        await event_bus_spy.publish(
            Event(
                event_type=EventType.ORDER_CREATED.value,
                data={"id_order": 123},
                metadata={
                    "actor_id": 1,
                    "actor_username": "admin",
                    "actor_role": "ADMIN",
                    "ip_address": "1.2.3.4",
                    "request_id": "rid-1",
                },
            )
        )

    from src.models.audit_log import AuditLog

    rows = db_session.query(AuditLog).all()
    assert len(rows) >= 1
    row = rows[-1]
    assert row.action == "order.create"
    assert row.resource_id == "123"
    assert row.actor_id == 1
    assert row.level == "standard"
    assert row.ip_address == "1.2.3.4"


def test_list_audit_logs_requires_permission(audit_denied_client: TestClient):
    response = audit_denied_client.get("/api/v1/audit-logs/")
    assert response.status_code == 403


def test_list_and_get_audit_logs_full_access(audit_admin_client: TestClient, db_session):
    log = create_audit_log(
        actor_id=5,
        actor_username="other",
        action="customer.update",
        resource_type="customer",
        resource_id="9",
        level="standard",
        ip_address="9.9.9.9",
        request_id="abc",
        changes={"before": {"a": 1}, "after": {"a": 2}},
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)

    # Point repository session to test db via override_get_db already in test_app
    list_resp = audit_admin_client.get("/api/v1/audit-logs/")
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["status"] == "success"
    assert body["count"] >= 1
    assert any(item["id_audit_log"] == log.id_audit_log for item in body["data"])
    item = next(i for i in body["data"] if i["id_audit_log"] == log.id_audit_log)
    assert item["ip_address"] == "9.9.9.9"
    assert item["request_id"] == "abc"
    assert item["changes"] == {"before": {"a": 1}, "after": {"a": 2}}
    assert item["actor_id"] == 5

    detail = audit_admin_client.get(f"/api/v1/audit-logs/{log.id_audit_log}")
    assert detail.status_code == 200
    assert detail.json()["action"] == "customer.update"


def test_detail_denied_without_permission(audit_denied_client: TestClient, db_session):
    log = create_audit_log()
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)

    response = audit_denied_client.get(f"/api/v1/audit-logs/{log.id_audit_log}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_audit_write_failure_does_not_break_publish(event_bus_spy: EventBusSpy):
    await register_audit_handlers(event_bus_spy)

    mock_session = type("S", (), {})()
    # Use MagicMock-like behavior via patch
    from unittest.mock import MagicMock

    broken = MagicMock()
    broken.commit.side_effect = RuntimeError("boom")

    with patch(
        "src.services.audit.audit_log_handler.SessionLocal", return_value=broken
    ):
        await event_bus_spy.publish(
            Event(
                event_type=EventType.CUSTOMER_CREATED.value,
                data={"id_customer": 1},
                metadata={"actor_id": 1, "actor_username": "a", "actor_role": "ADMIN"},
            )
        )

    # Event was recorded by spy even if audit write failed
    assert len(event_bus_spy.get_events_by_type(EventType.CUSTOMER_CREATED.value)) == 1
