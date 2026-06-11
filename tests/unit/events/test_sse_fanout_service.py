"""Unit tests — SSE fan-out service."""

import asyncio

import pytest

from src.events.core.event import Event, EventType
from src.events.sse.sse_fanout_service import SseFanoutService


@pytest.mark.asyncio
async def test_on_event_broadcasts_formatted_sse_message():
    service = SseFanoutService()
    client = await service.register(user_id=1)

    event = Event(
        event_type=EventType.ORDER_TRACKING_UPDATED.value,
        data={
            "id_order": 48564,
            "tracking": "BRT123",
            "awb": "BRT123",
            "source": "fastldv",
        },
    )
    await service.on_event(event)

    message = await asyncio.wait_for(client.queue.get(), timeout=1.0)
    assert "event: order.tracking.updated" in message
    assert '"id_order": 48564' in message
    assert '"tracking": "BRT123"' in message
    assert '"awb": "BRT123"' in message


@pytest.mark.asyncio
async def test_on_event_ignores_other_event_types():
    service = SseFanoutService()
    client = await service.register(user_id=1)

    await service.on_event(
        Event(
            event_type=EventType.ORDER_UPDATED.value,
            data={"order_id": 1},
        )
    )

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(client.queue.get(), timeout=0.1)
