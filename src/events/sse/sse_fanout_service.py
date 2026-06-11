"""In-memory SSE fan-out bridge subscribed to the application EventBus."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator, Dict
from uuid import uuid4

from src.events.core.event import Event, EventType
from src.events.core.event_bus import EventBus

logger = logging.getLogger(__name__)

KEEPALIVE_INTERVAL_SECONDS = 30
CLIENT_QUEUE_MAXSIZE = 100


@dataclass(slots=True)
class SseClient:
    """Registered browser connection waiting for SSE payloads."""

    id: str
    user_id: int
    queue: asyncio.Queue[str]


class SseFanoutService:
    """Broadcasts selected EventBus events to connected SSE clients."""

    def __init__(self) -> None:
        self._clients: Dict[str, SseClient] = {}
        self._lock = asyncio.Lock()

    async def on_event(self, event: Event) -> None:
        if event.event_type != EventType.ORDER_TRACKING_UPDATED.value:
            return
        await self.broadcast(self._format_sse_message(event))

    async def register(self, user_id: int) -> SseClient:
        client = SseClient(
            id=str(uuid4()),
            user_id=user_id,
            queue=asyncio.Queue(maxsize=CLIENT_QUEUE_MAXSIZE),
        )
        async with self._lock:
            self._clients[client.id] = client
        logger.debug("SSE client registered id=%s user_id=%s", client.id, user_id)
        return client

    async def unregister(self, client_id: str) -> None:
        async with self._lock:
            removed = self._clients.pop(client_id, None)
        if removed:
            logger.debug("SSE client unregistered id=%s", client_id)

    async def broadcast(self, message: str) -> None:
        async with self._lock:
            clients = list(self._clients.values())

        for client in clients:
            try:
                client.queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning(
                    "SSE queue full for client %s (user_id=%s), dropping message",
                    client.id,
                    client.user_id,
                )

    async def stream(self, client: SseClient) -> AsyncIterator[str]:
        try:
            while True:
                try:
                    message = await asyncio.wait_for(
                        client.queue.get(),
                        timeout=KEEPALIVE_INTERVAL_SECONDS,
                    )
                    yield message
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            await self.unregister(client.id)

    @staticmethod
    def _format_sse_message(event: Event) -> str:
        payload = {
            "id_order": event.data.get("id_order"),
            "tracking": event.data.get("tracking"),
            "awb": event.data.get("awb"),
            "source": event.data.get("source", "fastldv"),
            "timestamp": event.timestamp.isoformat(),
        }
        data_json = json.dumps(payload, ensure_ascii=False)
        return f"event: {event.event_type}\ndata: {data_json}\n\n"


async def attach_sse_fanout(event_bus: EventBus, service: SseFanoutService) -> None:
    """Subscribe the SSE bridge to tracking update events."""
    await event_bus.subscribe(
        EventType.ORDER_TRACKING_UPDATED.value,
        service.on_event,
    )
    logger.info("SSE fan-out attached to EventBus for %s", EventType.ORDER_TRACKING_UPDATED.value)
