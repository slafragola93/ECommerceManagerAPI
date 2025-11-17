"""
Platform State Sync Plugin

Sincronizza automaticamente gli stati di ordini e spedizioni con le piattaforme ecommerce
quando cambiano.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from src.events.interfaces import BaseEventHandler, EventHandlerPlugin
from src.events.plugins.platform_state_sync.handlers import PlatformStateSyncHandler


class PlatformStateSyncPlugin(EventHandlerPlugin):
    """Plugin per sincronizzazione automatica stati con piattaforme ecommerce."""
    
    def __init__(self, *, settings: Optional[Dict[str, str]] = None) -> None:
        super().__init__(name="PlatformStateSyncPlugin")
        self._settings = settings or {}
        self._handlers: List[BaseEventHandler] = [PlatformStateSyncHandler()]
    
    def get_handlers(self) -> List[BaseEventHandler]:
        """Return list of event handlers provided by this plugin."""
        return self._handlers
    
    def get_metadata(self) -> Dict[str, str]:
        """Return plugin metadata."""
        return {
            "version": "1.0.0",
            "category": "sync",
            "description": "Auto-sync order and shipping states with ecommerce platforms",
            **self._settings,
        }


def get_plugin() -> EventHandlerPlugin:
    """Factory function to get plugin instance."""
    return PlatformStateSyncPlugin()


PLUGIN_CLASS = PlatformStateSyncPlugin

