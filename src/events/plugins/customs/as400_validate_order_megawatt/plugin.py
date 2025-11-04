"""Entry point plugin validazione AS400."""

from typing import List
from src.events.interfaces import BaseEventHandler, EventHandlerPlugin
from src.events.plugins.customs.as400_validate_order_megawatt.handlers.validation_handler import AS400ValidationHandler


class AS400ValidationPlugin(EventHandlerPlugin):
    """Plugin per validare ordini con web service AS400."""

    def __init__(self):
        """Inizializza il plugin."""
        super().__init__(name="as400_validate_order_megawatt")
        self._handlers: List[BaseEventHandler] = [AS400ValidationHandler()]

    def get_handlers(self) -> List[BaseEventHandler]:
        """Recupera lista degli event handlers esposti da questo plugin."""
        return self._handlers

    def get_metadata(self) -> dict:
        """Recupera metadati del plugin."""
        return {
            "version": "1.0.0",
            "description": "Plugin validazione ordini AS400 per integrazione Megawatt",
            "category": "integration",
            "author": "ECommerceManagerAPI"
        }


def get_plugin() -> EventHandlerPlugin:
    """Funzione factory per creare istanza del plugin."""
    return AS400ValidationPlugin()


# Export alternativo per plugin loader
PLUGIN_CLASS = AS400ValidationPlugin

