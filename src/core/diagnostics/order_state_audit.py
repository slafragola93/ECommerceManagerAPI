"""
Diagnostic listener for Order.id_order_state writes.

Enabled only when env var ORDER_STATE_AUDIT=1 is set.

Logs every UPDATE that changes orders.id_order_state with:
- old_value -> new_value
- id_order
- Stack trace (project frames only) so we can pinpoint the caller
- Request URL (best-effort, via contextvar set by middleware)

Output goes to logs/order_state_audit.log so it does not pollute the main log.

Usage:
    PowerShell:
        $env:ORDER_STATE_AUDIT="1"; uvicorn src.main:app --host 0.0.0.0 --port 8000

After reproducing the bug, share logs/order_state_audit.log to get an exact
caller for every write to id_order_state.
"""
from __future__ import annotations

import logging
import os
import traceback
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

from sqlalchemy import event, inspect

from src.models.order import Order

current_request_url: ContextVar[Optional[str]] = ContextVar(
    "current_request_url", default=None
)
current_request_method: ContextVar[Optional[str]] = ContextVar(
    "current_request_method", default=None
)

_audit_logger: Optional[logging.Logger] = None
_AUDIT_ENV_VAR = "ORDER_STATE_AUDIT"


def is_audit_enabled() -> bool:
    return os.getenv(_AUDIT_ENV_VAR, "0").strip().lower() in {"1", "true", "yes", "on"}


def _build_audit_logger() -> logging.Logger:
    logger = logging.getLogger("order_state_audit")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(
        log_dir / "order_state_audit.log", encoding="utf-8"
    )
    formatter = logging.Formatter(
        "%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        logging.Formatter("[ORDER_STATE_AUDIT] %(message)s")
    )
    logger.addHandler(stream_handler)

    return logger


def _format_project_stack() -> str:
    """Return a compact stack trace limited to project frames (src/...)."""
    frames = traceback.extract_stack()
    project_frames = [
        f
        for f in frames
        if "src" in f.filename.replace("\\", "/").split("/")
        and "diagnostics/order_state_audit" not in f.filename.replace("\\", "/")
    ]
    if not project_frames:
        return "<no project frames found>"
    tail = project_frames[-12:]
    return "\n".join(
        f"    {f.filename}:{f.lineno} in {f.name}() -> {f.line}" for f in tail
    )


def _on_before_update(mapper, connection, target: Order) -> None:
    state = inspect(target)
    history = state.attrs.id_order_state.history
    if not history.has_changes():
        return

    old_value = history.deleted[0] if history.deleted else None
    new_value = history.added[0] if history.added else target.id_order_state

    if old_value == new_value:
        return

    logger = _audit_logger
    if logger is None:
        return

    url = current_request_url.get()
    method = current_request_method.get()

    logger.info(
        "id_order=%s | %s -> %s | %s %s\n%s\n%s",
        getattr(target, "id_order", "?"),
        old_value,
        new_value,
        method or "<no-request>",
        url or "<no-url>",
        "Stack:",
        _format_project_stack(),
    )


def setup_order_state_audit() -> None:
    """
    Idempotent setup. Safe to call once at app startup.

    No-op if ORDER_STATE_AUDIT env var is not set.
    """
    global _audit_logger
    if not is_audit_enabled():
        return

    if _audit_logger is not None:
        return

    _audit_logger = _build_audit_logger()
    event.listen(Order, "before_update", _on_before_update)
    _audit_logger.info(
        "===== Order state audit listener ENABLED ====="
    )
    print("[ORDER_STATE_AUDIT] listener enabled (logs/order_state_audit.log)")
