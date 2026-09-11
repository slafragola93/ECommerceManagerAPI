"""Retry HTTP transient verso FatturaPA.com (timeout, rete, 429/5xx)."""
from __future__ import annotations

import httpx

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (0.5, 1.0)


def is_retryable_status(status_code: int) -> bool:
    return int(status_code) in RETRYABLE_STATUS


def is_retryable_exception(exc: BaseException) -> bool:
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError))


def retry_delay_seconds(failed_attempt_index: int) -> float:
    """Backoff dopo il tentativo `failed_attempt_index` (0-based)."""
    if failed_attempt_index < 0:
        return BACKOFF_SECONDS[0]
    if failed_attempt_index >= len(BACKOFF_SECONDS):
        return BACKOFF_SECONDS[-1]
    return BACKOFF_SECONDS[failed_attempt_index]


def should_retry_status(status_code: int, attempt_index: int) -> bool:
    """True se si può ritentare dopo questa risposta (attempt_index 0-based)."""
    return is_retryable_status(status_code) and attempt_index < (MAX_ATTEMPTS - 1)
