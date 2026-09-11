"""Unit test — STEP 1: upload_stop rispetta send_to_sdi (UploadStop vs UploadStop1)."""
from unittest.mock import AsyncMock

import pytest

from src.services.external.fatturapa_service import FatturaPAService


@pytest.fixture
def fatturapa_service():
    svc = FatturaPAService.__new__(FatturaPAService)
    svc.base_url = "https://api.fatturapa.com/ws/V10.svc/rest"
    svc.api_key = "test-api-key"
    return svc


class TestUploadStopEndpoint:
    def test_false_uses_upload_stop1_only(self):
        endpoint = FatturaPAService.upload_stop_endpoint(False)
        assert endpoint == "UploadStop1"
        assert endpoint != "UploadStop"

    def test_true_uses_upload_stop_not_stop1(self):
        endpoint = FatturaPAService.upload_stop_endpoint(True)
        assert endpoint == "UploadStop"
        assert "1" not in endpoint


class TestUploadStopHttp:
    @pytest.mark.asyncio
    async def test_send_to_sdi_false_calls_upload_stop1(self, fatturapa_service):
        fatturapa_service._http_request = AsyncMock(
            return_value=(200, "application/json", '{"status":"ok"}')
        )

        result = await fatturapa_service.upload_stop("blob-name", send_to_sdi=False)

        fatturapa_service._http_request.assert_awaited_once()
        method, url = fatturapa_service._http_request.await_args.args[:2]
        assert method == "GET"
        assert url.endswith("/UploadStop1/test-api-key/blob-name")
        assert "/UploadStop/" not in url
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_send_to_sdi_true_calls_upload_stop(self, fatturapa_service):
        fatturapa_service._http_request = AsyncMock(
            return_value=(200, "application/json", '{"status":"ok"}')
        )

        result = await fatturapa_service.upload_stop("blob-name", send_to_sdi=True)

        fatturapa_service._http_request.assert_awaited_once()
        method, url = fatturapa_service._http_request.await_args.args[:2]
        assert method == "GET"
        assert url.endswith("/UploadStop/test-api-key/blob-name")
        assert "/UploadStop1/" not in url
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_http_error_returns_error_status(self, fatturapa_service):
        fatturapa_service._http_request = AsyncMock(
            return_value=(500, "text/plain", "internal error")
        )

        result = await fatturapa_service.upload_stop("blob-name", send_to_sdi=True)

        assert result["status"] == "error"
        assert "internal error" in result["message"]

    @pytest.mark.asyncio
    async def test_upload_fiscal_xml_pipeline(self, fatturapa_service):
        fatturapa_service.upload_start = AsyncMock(
            return_value=("blob-name", "https://blob/complete")
        )
        fatturapa_service.upload_xml = AsyncMock(return_value=True)
        fatturapa_service.upload_stop = AsyncMock(return_value={"status": "ok"})

        result = await fatturapa_service.upload_fiscal_xml(
            "IT02046570426_000001.xml", "<xml/>", send_to_sdi=True
        )

        fatturapa_service.upload_start.assert_awaited_once()
        fatturapa_service.upload_xml.assert_awaited_once()
        fatturapa_service.upload_stop.assert_awaited_once_with(
            "blob-name", send_to_sdi=True
        )
        assert result["status"] == "ok"
