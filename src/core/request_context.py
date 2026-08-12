"""
Request-scoped context (ContextVar) for audit and correlation.

Populated by ErrorLoggingMiddleware (request_id, ip) and get_current_user (actor).
Read by emit_event_on_success enrichment and AuditLogHandler.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class RequestActor:
    actor_id: Optional[int]
    username: str
    role: str


_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_ip_address: ContextVar[Optional[str]] = ContextVar("ip_address", default=None)
_actor: ContextVar[Optional[RequestActor]] = ContextVar("request_actor", default=None)


def set_request_id(value: Optional[str]) -> Token:
    return _request_id.set(value)


def get_request_id() -> Optional[str]:
    return _request_id.get()


def reset_request_id(token: Token) -> None:
    _request_id.reset(token)


def set_ip_address(value: Optional[str]) -> Token:
    return _ip_address.set(value)


def get_ip_address() -> Optional[str]:
    return _ip_address.get()


def reset_ip_address(token: Token) -> None:
    _ip_address.reset(token)


def set_actor(
    actor_id: Optional[int],
    username: str = "system",
    role: str = "",
) -> Token:
    return _actor.set(RequestActor(actor_id=actor_id, username=username, role=role))


def get_actor() -> Optional[RequestActor]:
    return _actor.get()


def reset_actor(token: Token) -> None:
    _actor.reset(token)


def clear_actor() -> None:
    _actor.set(None)


def get_audit_metadata() -> dict:
    """Snapshot for Event.metadata enrichment."""
    actor = get_actor()
    meta = {
        "request_id": get_request_id(),
        "ip_address": get_ip_address(),
    }
    if actor is not None:
        meta["actor_id"] = actor.actor_id
        meta["actor_username"] = actor.username
        meta["actor_role"] = actor.role
    else:
        meta["actor_id"] = None
        meta["actor_username"] = "system"
        meta["actor_role"] = ""
    return meta
