"""Retry HTTP transient su FatturaPA.com."""
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.services.external.fatturapa_http_retry import (
    MAX_ATTEMPTS,
    is_retryable_exception,
    is_retryable_status,
    should_retry_status,
)
from src.services.external.fatturapa_service import FatturaPAService


def test_retryable_status_only_transient():
    assert is_retryable_status(503) is True
    assert is_retryable_status(429) is True
    assert is_retryable_status(400) is False
    assert is_retryable_status(404) is False
    assert is_retryable_status(200) is False


def test_should_retry_stops_at_last_attempt():
    assert should_retry_status(503, 0) is True
    assert should_retry_status(503, MAX_ATTEMPTS - 1) is False


def test_retryable_exception_types():
    assert is_retryable_exception(httpx.TimeoutException("t")) is True
    assert is_retryable_exception(httpx.ConnectError("c")) is True
    assert is_retryable_exception(ValueError("no")) is False


class _FakeResponse:
    def __init__(self, status_code, text="ok"):
        self.status_code = status_code
        self.headers = {"content-type": "text/plain"}
        self.text = text


class _FakeClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, headers=None):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def fatturapa_service():
    svc = FatturaPAService.__new__(FatturaPAService)
    svc.timeout = 1
    svc.user_agent = "test-agent"
    return svc


@pytest.mark.asyncio
async def test_http_retries_503_then_succeeds(fatturapa_service):
    client = _FakeClient([_FakeResponse(503, "busy"), _FakeResponse(200, "ok")])
    with patch("src.services.external.fatturapa_service.httpx.AsyncClient", return_value=client):
        with patch(
            "src.services.external.fatturapa_service.asyncio.sleep",
            new=AsyncMock(),
        ):
            status, _, body = await fatturapa_service._http_request(
                "GET", "https://example.test/UploadStop"
            )
    assert status == 200
    assert body == "ok"
    assert client.calls == 2


@pytest.mark.asyncio
async def test_http_retries_timeout_then_succeeds(fatturapa_service):
    client = _FakeClient(
        [httpx.TimeoutException("timeout"), _FakeResponse(200, '{"ok":true}')]
    )
    with patch("src.services.external.fatturapa_service.httpx.AsyncClient", return_value=client):
        with patch(
            "src.services.external.fatturapa_service.asyncio.sleep",
            new=AsyncMock(),
        ):
            status, _, body = await fatturapa_service._http_request(
                "GET", "https://example.test/UploadStart1"
            )
    assert status == 200
    assert "ok" in body
    assert client.calls == 2


@pytest.mark.asyncio
async def test_http_does_not_retry_400(fatturapa_service):
    client = _FakeClient([_FakeResponse(400, "bad request")])
    with patch("src.services.external.fatturapa_service.httpx.AsyncClient", return_value=client):
        status, _, body = await fatturapa_service._http_request(
            "GET", "https://example.test/UploadStop"
        )
    assert status == 400
    assert client.calls == 1
    assert "bad request" in body


@pytest.mark.asyncio
async def test_http_gives_up_after_max_5xx(fatturapa_service):
    client = _FakeClient(
        [_FakeResponse(503, "a"), _FakeResponse(503, "b"), _FakeResponse(503, "c")]
    )
    with patch("src.services.external.fatturapa_service.httpx.AsyncClient", return_value=client):
        with patch(
            "src.services.external.fatturapa_service.asyncio.sleep",
            new=AsyncMock(),
        ):
            status, _, body = await fatturapa_service._http_request(
                "GET", "https://example.test/UploadStop"
            )
    assert status == 503
    assert client.calls == MAX_ATTEMPTS
    assert body == "c"
