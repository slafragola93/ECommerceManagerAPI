"""
Platform State Sync Plugin

Sincronizza automaticamente gli stati di ordini e spedizioni con le piattaforme ecommerce.
"""
from src.events.plugins.platform_state_sync.plugin import get_plugin, PLUGIN_CLASS

__all__ = ["get_plugin", "PLUGIN_CLASS"]

