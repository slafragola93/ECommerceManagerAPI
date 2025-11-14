"""
Stock Auto-Update Plugin

Automatically decrements product.quantity when orders are created.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from src.events.interfaces import BaseEventHandler, EventHandlerPlugin
from src.events.plugins.stock_auto_update.handlers import StockAutoUpdateHandler


class StockAutoUpdatePlugin(EventHandlerPlugin):
    """Plugin for automatic stock updates on order creation."""
    
    def __init__(self, *, settings: Optional[Dict[str, str]] = None) -> None:
        super().__init__(name="StockAutoUpdatePlugin")
        self._settings = settings or {}
        self._handlers: List[BaseEventHandler] = [StockAutoUpdateHandler()]
    
    def get_handlers(self) -> List[BaseEventHandler]:
        """Return list of event handlers provided by this plugin."""
        return self._handlers
    
    def get_metadata(self) -> Dict[str, str]:
        """Return plugin metadata."""
        return {
            "version": "1.0.0",
            "category": "inventory",
            "description": "Auto-decrement product stock on order creation",
            **self._settings,
        }


def get_plugin() -> EventHandlerPlugin:
    """Factory function to get plugin instance."""
    return StockAutoUpdatePlugin()


PLUGIN_CLASS = StockAutoUpdatePlugin


