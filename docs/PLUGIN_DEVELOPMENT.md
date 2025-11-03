# Plugin Development Guide

This guide explains how to build and distribute event plugins for the order management system.

## Plugin Structure

A plugin is a Python module (package or single file) that exports an implementation of `EventHandlerPlugin`.

Example directory layout:

```
my_plugin/
  __init__.py
  plugin.py
  requirements.txt   # optional dependencies
```

`plugin.py` must expose either:

- a callable named `get_plugin()` / `create_plugin()` returning an `EventHandlerPlugin`, or
- a class assigned to `PLUGIN_CLASS` inheriting from `EventHandlerPlugin`.

## Implementing a Plugin

```python
from src.events.interfaces import EventHandlerPlugin, BaseEventHandler
from src.events.core.event import EventType


class OrderNotificationHandler(BaseEventHandler):
    def __init__(self) -> None:
        super().__init__(name="order_notification_handler")

    def can_handle(self, event):
        return event.event_type == EventType.ORDER_STATUS_CHANGED.value

    async def handle(self, event):
        # Implement business logic here
        ...


class OrderNotificationPlugin(EventHandlerPlugin):
    def get_handlers(self):
        return [OrderNotificationHandler()]


def get_plugin():
    return OrderNotificationPlugin()
```

### Naming Guidelines

- Handler names (`BaseEventHandler.name`) must be unique across all loaded plugins.
- Use snake_case identifiers for handlers to simplify configuration references.

## Configuration

- Place the plugin inside one of the directories listed in `config/event_handlers.yaml -> plugin_directories`.
- Enable/disable handlers under `enabled_handlers` or `disabled_handlers`.
- Route handlers to specific order states via `routes.order_status_changed`:

```yaml
routes:
  order_status_changed:
    1:
      - order_notification_handler
    "*":
      - fallback_handler
```

Use `POST /api/v1/events/reload-config` to apply changes at runtime without restarting the application.

## Marketplace Packaging

To distribute a plugin through the marketplace:

1. Package files into a ZIP archive preserving the plugin root directory.
2. Include `requirements.txt` if the plugin requires extra dependencies.
3. Provide metadata endpoint fields used by the installer:
   - `download_url` (required)
   - `checksum_sha256` (optional but recommended)

## Runtime Considerations

- Handlers run concurrently; ensure thread-safety for shared resources.
- Use `event.metadata["idempotency_key"]` to avoid duplicate side-effects.
- Exceptions inside handlers are logged and wrapped in `HandlerExecutionError`; they do not block other handlers.

## Testing Plugins

- Add unit tests mirroring `test/events/test_plugin_manager.py` to validate integration.
- Use the `PluginInstaller` CLI endpoints to install the plugin in non-production environments before rollout.

