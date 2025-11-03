"""HTTP client integration with the external plugin marketplace."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from ..config.config_schema import MarketplaceSettings


class MarketplaceClient:
    """Thin wrapper around the remote marketplace API."""

    def __init__(self, settings: MarketplaceSettings) -> None:
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return self._settings.enabled

    async def list_plugins(self) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []

        url = self._build_url("/plugins")
        response = await self._request("GET", url)
        data = response.json()
        if not isinstance(data, list):
            raise ValueError("Marketplace response is not a list")
        return data

    async def get_plugin_metadata(self, name: str) -> Dict[str, Any]:
        if not self.enabled:
            raise ValueError("Marketplace integration is disabled")

        url = self._build_url(f"/plugins/{name}")
        response = await self._request("GET", url)
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Marketplace plugin metadata must be a JSON object")
        return data

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        timeout = self._settings.download_timeout_seconds
        headers = self._build_headers()
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response

    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Accept": "application/json"}
        if self._settings.api_key:
            headers["Authorization"] = f"Bearer {self._settings.api_key}"
        return headers

    def _build_url(self, path: str) -> str:
        base = self._settings.base_url.rstrip("/")
        suffix = path if path.startswith("/") else f"/{path}"
        return f"{base}{suffix}"

