"""Core audit infrastructure (EventBus subscriber, not a plugin)."""

from src.services.audit.register import register_audit_handlers

__all__ = ["register_audit_handlers"]
