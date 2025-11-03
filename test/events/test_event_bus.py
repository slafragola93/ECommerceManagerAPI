import pytest

from src.events.core.event import Event, EventType
from src.events.core.event_bus import EventBus
from src.events.core.exceptions import HandlerExecutionError


@pytest.mark.asyncio
async def test_event_bus_invokes_all_handlers():
    bus = EventBus()
    results: list[int] = []

    async def handler_one(event: Event) -> None:
        results.append(event.data["value"])

    async def handler_two(event: Event) -> None:
        results.append(event.data["value"] * 2)

    await bus.subscribe(EventType.ORDER_STATUS_CHANGED.value, handler_one)
    await bus.subscribe(EventType.ORDER_STATUS_CHANGED.value, handler_two)

    await bus.publish(Event(event_type=EventType.ORDER_STATUS_CHANGED.value, data={"value": 5}))

    assert results == [5, 10]


@pytest.mark.asyncio
async def test_event_bus_collects_handler_errors():
    bus = EventBus()
    called: list[str] = []

    async def failing_handler(_: Event) -> None:
        raise RuntimeError("boom")

    async def succeeding_handler(event: Event) -> None:
        called.append("ok")

    await bus.subscribe(EventType.ORDER_STATUS_CHANGED.value, failing_handler)
    await bus.subscribe(EventType.ORDER_STATUS_CHANGED.value, succeeding_handler)

    with pytest.raises(HandlerExecutionError):
        await bus.publish(Event(event_type=EventType.ORDER_STATUS_CHANGED.value, data={}))

    assert called == ["ok"]

