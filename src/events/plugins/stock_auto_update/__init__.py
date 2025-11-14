"""
Stock Auto-Update Plugin

Plugin event-driven che decrementa automaticamente product.quantity
quando vengono creati ordini.
"""

from src.events.plugins.stock_auto_update.plugin import StockAutoUpdatePlugin, get_plugin

__all__ = ["StockAutoUpdatePlugin", "get_plugin"]
__version__ = "1.0.0"

