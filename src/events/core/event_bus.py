"""Asynchronous event bus implementation."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Awaitable, Callable, Dict, Iterable, Optional

from .event import Event
from .exceptions import HandlerExecutionError, HandlerFailure

logger = logging.getLogger(__name__)

EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    """Thread-safe asynchronous event bus."""

    def __init__(
        self,
        *,
        max_concurrent_handlers: Optional[int] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        self._handlers: Dict[str, set[EventHandler]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._loop = loop
        self._semaphore = (
            asyncio.Semaphore(max_concurrent_handlers)
            if max_concurrent_handlers and max_concurrent_handlers > 0
            else None
        )

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for the specified event type."""

        if not asyncio.iscoroutinefunction(handler):
            raise TypeError("Event handler must be an async function")

        async with self._lock:
            self._handlers[event_type].add(handler)
            logger.debug("Handler %s subscribed to event '%s'", handler, event_type)

    async def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler for the specified event type."""

        async with self._lock:
            handlers = self._handlers.get(event_type)
            if handlers and handler in handlers:
                handlers.remove(handler)
                logger.debug(
                    "Handler %s unsubscribed from event '%s'", handler, event_type
                )
            if handlers and not handlers:
                self._handlers.pop(event_type, None)

    async def publish(self, event: Event) -> None:
        """Emit an event to all registered handlers."""

        async with self._lock:
            handlers: Iterable[EventHandler] = tuple(
                self._handlers.get(event.event_type, ())
            )

        if not handlers:
            logger.debug("No handlers registered for event '%s'", event.event_type)
            return

        await self._dispatch(event, handlers)

    async def _dispatch(
        self, event: Event, handlers: Iterable[EventHandler]
    ) -> None:
        """Dispatch the event to all handlers and isolate failures."""

        async def _run_handler(handler: EventHandler) -> None:
            if self._semaphore:
                async with self._semaphore:
                    await self._execute_handler(handler, event)
            else:
                await self._execute_handler(handler, event)

        awaitables = [_run_handler(handler) for handler in handlers]
        results = await asyncio.gather(*awaitables, return_exceptions=True)

        failures: list[HandlerFailure] = []
        for handler, result in zip(handlers, results):
            if isinstance(result, HandlerExecutionError):
                failures.extend(result.failures)
            elif isinstance(result, Exception):
                failures.append(HandlerFailure(handler=handler, event=event, exception=result))

        for failure in failures:
            logger.exception(
                "Error while executing handler %s for event '%s'",
                failure.handler,
                failure.event,
                exc_info=failure.exception,
            )

        if failures:
            raise HandlerExecutionError.merge(failures)

    async def _execute_handler(self, handler: EventHandler, event: Event) -> None:
        """Execute a single handler with proper error handling."""

        try:
            await handler(event)
        except HandlerExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - maintain backward compat
            raise HandlerExecutionError.from_single(
                handler=handler, event=event, original_exc=exc
            )

