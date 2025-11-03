import textwrap

import pytest

from src.events.config import EventConfigLoader
from src.events.config.config_schema import EventConfig
from src.events.core.event import Event, EventType
from src.events.core.event_bus import EventBus
from src.events.plugin_loader import PluginLoader
from src.events.plugin_manager import PluginManager


@pytest.mark.asyncio
async def test_plugin_manager_loads_and_executes_handlers(tmp_path):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    plugin_pkg = plugin_dir / "sample_plugin"
    plugin_pkg.mkdir()
    (plugin_pkg / "__init__.py").write_text("", encoding="utf-8")
    (plugin_pkg / "plugin.py").write_text(
        textwrap.dedent(
            """
            from src.events.interfaces import EventHandlerPlugin, BaseEventHandler
            from src.events.core.event import EventType


            class SampleHandler(BaseEventHandler):
                def __init__(self):
                    super().__init__(name="sample_handler")

                def can_handle(self, event):
                    return event.event_type == EventType.ORDER_STATUS_CHANGED.value

                async def handle(self, event):
                    event.data.setdefault("log", []).append(self.name)


            class Plugin(EventHandlerPlugin):
                def get_handlers(self):
                    return [SampleHandler()]
            """
        ),
        encoding="utf-8",
    )

    config_path = tmp_path / "event_config.yaml"
    loader = EventConfigLoader(config_path)
    config = EventConfig(plugin_directories=[str(plugin_dir)])
    loader.save(config)

    event_bus = EventBus()
    plugin_loader = PluginLoader(config.plugin_directories)
    manager = PluginManager(event_bus, loader, plugin_loader)

    await manager.initialise()

    assert "sample_plugin" in manager.get_loaded_plugins()

    event = Event(event_type=EventType.ORDER_STATUS_CHANGED.value, data={})
    await event_bus.publish(event)

    assert event.data.get("log") == ["sample_handler"]

