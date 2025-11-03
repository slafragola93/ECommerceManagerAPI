"""Utility to manage loading and saving the event configuration."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Optional

import yaml
from pydantic import ValidationError

from .config_schema import EventConfig


class EventConfigLoader:
    """Handle loading, caching and persisting the event configuration."""

    def __init__(self, config_path: str | Path) -> None:
        self._path = Path(config_path)
        self._lock = threading.RLock()
        self._cached_config: Optional[EventConfig] = None

    @property
    def path(self) -> Path:
        return self._path

    def load(self, *, use_cache: bool = True) -> EventConfig:
        with self._lock:
            if use_cache and self._cached_config is not None:
                return self._cached_config.model_copy(deep=True)

            if not self._path.exists():
                raise FileNotFoundError(
                    f"Event configuration file '{self._path}' does not exist"
                )

            raw_config = self._read_yaml()
            config = EventConfig.model_validate(raw_config)
            self._cached_config = config
            return config.model_copy(deep=True)

    def refresh(self) -> EventConfig:
        return self.load(use_cache=False)

    def save(self, config: EventConfig) -> None:
        with self._lock:
            data = config.model_dump(mode="json")
            self._write_yaml(data)
            self._cached_config = config.model_copy(deep=True)

    def update(self, updates: Mapping[str, Any]) -> EventConfig:
        with self._lock:
            current = self.load(use_cache=True)
            raw = current.model_dump(mode="json")
            merged = _deep_merge(raw, dict(updates))
            try:
                new_config = EventConfig.model_validate(merged)
            except ValidationError as exc:
                raise ValueError("Invalid event configuration update") from exc

            self._write_yaml(new_config.model_dump(mode="json"))
            self._cached_config = new_config.model_copy(deep=True)
            return new_config

    def _read_yaml(self) -> MutableMapping[str, Any]:
        with self._path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
            if not isinstance(data, MutableMapping):
                raise ValueError("Event configuration must be a YAML mapping")
            return dict(data)

    def _write_yaml(self, data: Mapping[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, sort_keys=True, allow_unicode=True)
        temp_path.replace(self._path)


def _deep_merge(original: MutableMapping[str, Any], updates: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    result: MutableMapping[str, Any] = dict(original)
    for key, value in updates.items():
        if (
            key in result
            and isinstance(result[key], MutableMapping)
            and isinstance(value, MutableMapping)
        ):
            result[key] = _deep_merge(result[key], value)  # type: ignore[assignment]
        else:
            result[key] = value
    return result

