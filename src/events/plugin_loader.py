"""Dynamic loading utilities for event plugins."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Dict, Iterable, List, Optional

import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PluginDescriptor:
    """Basic metadata describing a plugin candidate."""

    name: str
    base_path: Path
    entrypoint: Path

    @property
    def source(self) -> str:
        return str(self.entrypoint)


class PluginLoader:
    """Responsible for discovering and importing plugin modules."""

    def __init__(self, directories: Optional[Iterable[str]] = None) -> None:
        self._directories: List[Path] = []
        self.set_directories(directories or [])

    @property
    def directories(self) -> List[Path]:
        return list(self._directories)

    def set_directories(self, directories: Iterable[str]) -> None:
        self._directories = [Path(directory) for directory in directories]

    def discover(self) -> Dict[str, PluginDescriptor]:
        """Discover plugins available in the configured directories."""

        discovered: Dict[str, PluginDescriptor] = {}
        for base_dir in self._directories:
            if not base_dir.exists() or not base_dir.is_dir():
                logger.debug("Plugin directory %s does not exist", base_dir)
                continue

            for candidate in base_dir.iterdir():
                if candidate.name.startswith("__"):
                    continue
                descriptor = self._build_descriptor(candidate)
                if descriptor is None:
                    continue

                if descriptor.name in discovered:
                    logger.warning(
                        "Plugin name '%s' already discovered at %s; skipping %s",
                        descriptor.name,
                        discovered[descriptor.name].source,
                        descriptor.source,
                    )
                    continue

                discovered[descriptor.name] = descriptor

        return discovered

    def load_module(self, descriptor: PluginDescriptor) -> ModuleType:
        """Import the module defined by the descriptor."""

        module_name = f"events_plugin_{descriptor.name}"
        spec = importlib.util.spec_from_file_location(module_name, descriptor.entrypoint)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load plugin '{descriptor.name}' from {descriptor.source}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def _build_descriptor(self, candidate: Path) -> Optional[PluginDescriptor]:
        if candidate.is_dir():
            entry = candidate / "plugin.py"
            if not entry.exists():
                entry = candidate / "__init__.py"
            if not entry.exists():
                return None
            return PluginDescriptor(name=candidate.name, base_path=candidate, entrypoint=entry)

        if candidate.is_file() and candidate.suffix == ".py":
            return PluginDescriptor(
                name=candidate.stem,
                base_path=candidate.parent,
                entrypoint=candidate,
            )

        return None

