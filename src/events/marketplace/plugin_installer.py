"""Utilities to install and uninstall plugins from the marketplace."""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from ..config import EventConfig, EventConfigLoader
from ..config.config_schema import MarketplaceSettings, PluginSettings
from ..plugin_manager import PluginManager
from .marketplace_client import MarketplaceClient


@dataclass(slots=True)
class PluginInstallRequest:
    name: str
    source_url: Optional[str] = None
    checksum_sha256: Optional[str] = None


class PluginInstaller:
    """Manage the download, installation and removal of plugins."""

    def __init__(
        self,
        config_loader: EventConfigLoader,
        plugin_manager: PluginManager,
        marketplace_client: Optional[MarketplaceClient] = None,
    ) -> None:
        self._config_loader = config_loader
        self._plugin_manager = plugin_manager
        self._marketplace_client = marketplace_client

    async def install(self, request: PluginInstallRequest) -> EventConfig:
        config = self._config_loader.load()
        marketplace_settings = config.marketplace

        download_url, checksum = await self._resolve_download_info(request, marketplace_settings)

        target_directory = self._resolve_target_directory(config)
        extracted_path = await self._download_and_extract(
            request.name,
            download_url,
            target_directory,
            checksum,
            marketplace_settings.download_timeout_seconds,
        )

        try:
            await self._install_requirements(extracted_path)
            updated_config = self._enable_plugin_in_config(config, request.name)
            self._config_loader.save(updated_config)
            await self._plugin_manager.reload()
            return updated_config
        except Exception:
            shutil.rmtree(extracted_path, ignore_errors=True)
            raise

    async def uninstall(self, plugin_name: str) -> EventConfig:
        config = self._config_loader.load()
        plugin_dir = self._locate_installed_plugin(config, plugin_name)
        if plugin_dir is None or not plugin_dir.exists():
            raise FileNotFoundError(f"Plugin '{plugin_name}' non trovato nelle directory configurate")

        shutil.rmtree(plugin_dir, ignore_errors=True)

        self._remove_plugin_from_config(config, plugin_name)
        self._config_loader.save(config)
        await self._plugin_manager.reload()
        return config

    async def list_marketplace_plugins(self) -> list[dict[str, Any]]:
        if not self._marketplace_client or not self._marketplace_client.enabled:
            return []
        return await self._marketplace_client.list_plugins()

    async def _resolve_download_info(
        self,
        request: PluginInstallRequest,
        marketplace_settings: MarketplaceSettings,
    ) -> tuple[str, Optional[str]]:
        if request.source_url:
            return request.source_url, request.checksum_sha256

        if not self._marketplace_client or not self._marketplace_client.enabled:
            raise ValueError("Marketplace non configurato e source_url non fornito")

        metadata = await self._marketplace_client.get_plugin_metadata(request.name)
        download_url = metadata.get("download_url")
        if not download_url:
            raise ValueError("Marketplace metadata non contiene 'download_url'")
        checksum = metadata.get("checksum_sha256")
        return download_url, checksum

    def _resolve_target_directory(self, config: EventConfig) -> Path:
        for directory in reversed(config.plugin_directories):
            path = Path(directory)
            try:
                path.mkdir(parents=True, exist_ok=True)
                if os.access(path, os.W_OK):
                    return path
            except OSError:
                continue
        raise RuntimeError("Nessuna directory plugin scrivibile trovata")

    async def _download_and_extract(
        self,
        plugin_name: str,
        url: str,
        target_directory: Path,
        checksum_sha256: Optional[str],
        timeout_seconds: int,
    ) -> Path:
        tmp_dir = Path(tempfile.mkdtemp(prefix="plugin_download_"))
        archive_path = tmp_dir / f"{plugin_name}.zip"

        try:
            await self._download_file(url, archive_path, timeout_seconds)

            if checksum_sha256:
                self._verify_checksum(archive_path, checksum_sha256)

            extract_path = target_directory / plugin_name
            if extract_path.exists():
                shutil.rmtree(extract_path)

            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(extract_path)

            return extract_path
        except Exception:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise
        finally:
            archive_path.unlink(missing_ok=True)

    async def _download_file(self, url: str, destination: Path, timeout_seconds: int) -> None:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with destination.open("wb") as file_handle:
                    async for chunk in response.aiter_bytes():
                        file_handle.write(chunk)

    def _verify_checksum(self, file_path: Path, expected_checksum: str) -> None:
        sha256 = hashlib.sha256()
        with file_path.open("rb") as file_handle:
            for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
                sha256.update(chunk)
        digest = sha256.hexdigest()
        if digest.lower() != expected_checksum.lower():
            raise ValueError("Checksum SHA256 del pacchetto non corrisponde")

    async def _install_requirements(self, plugin_path: Path) -> None:
        requirements = plugin_path / "requirements.txt"
        if not requirements.exists():
            return

        def _install() -> None:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(requirements)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        await asyncio.to_thread(_install)

    def _enable_plugin_in_config(self, config: EventConfig, plugin_name: str) -> EventConfig:
        config = config.model_copy(deep=True)
        existing = config.plugins.get(plugin_name)
        payload: Dict[str, Any] = (
            existing.model_dump() if isinstance(existing, PluginSettings) else {}
        )
        payload["enabled"] = True
        config.plugins[plugin_name] = PluginSettings(**payload)

        if plugin_name in config.disabled_handlers:
            config.disabled_handlers.remove(plugin_name)
        if plugin_name not in config.enabled_handlers:
            config.enabled_handlers.append(plugin_name)

        return config

    def _remove_plugin_from_config(self, config: EventConfig, plugin_name: str) -> None:
        config.plugins.pop(plugin_name, None)
        if plugin_name in config.enabled_handlers:
            config.enabled_handlers.remove(plugin_name)
        if plugin_name in config.disabled_handlers:
            config.disabled_handlers.remove(plugin_name)

    def _locate_installed_plugin(self, config: EventConfig, plugin_name: str) -> Optional[Path]:
        for directory in config.plugin_directories:
            candidate = Path(directory) / plugin_name
            if candidate.exists():
                return candidate
        return None

