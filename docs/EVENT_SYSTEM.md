# Event System Overview

This document describes the event-driven architecture introduced for order state changes.

## Key Components

- **EventBus** (`src/events/core/event_bus.py`)
  - Asynchronous, thread-safe publish/subscribe bus
  - Supports multiple handlers per event with error isolation
- **Event** (`src/events/core/event.py`)
  - Immutable data structure carrying `event_type`, `data`, `metadata` (with auto `idempotency_key`)
- **PluginManager** (`src/events/plugin_manager.py`)
  - Loads plugins from configured directories, manages lifecycle, applies routing rules
  - Subscribes handlers to the EventBus and resolves routing rules at runtime
- **Configuration** (`config/event_handlers.yaml`)
  - Controls plugin directories, enabled/disabled handlers, routing and marketplace settings
- **Runtime Helpers** (`src/events/runtime.py`)
  - Stores singletons (EventBus, PluginManager, config loader, marketplace client)
- **Marketplace Integration** (`src/events/marketplace/`)
  - Optional: download/install/remove plugins from an external marketplace

## Event Flow

1. Order state changes trigger `EventType.ORDER_STATUS_CHANGED` via repository/router logic.
2. `emit_event()` publishes the event on the EventBus.
3. PluginManager resolves applicable handlers based on routing and configuration.
4. Handlers execute concurrently; failures are collected without blocking others.

## Configuration Lifecycle

- Configuration is loaded at startup via `EventConfigLoader`.
- Routes, handler enablement and plugin directories can be reloaded at runtime through the `/api/v1/events/*` endpoints.
- Marketplace endpoints allow installing/uninstalling external plugins, updating configuration automatically.

## Default Setup

`config/event_handlers.yaml` ships with:

```yaml
plugin_directories:
  - src/events/plugins
  - /opt/custom_plugins
routes:
  order_status_changed: {}
marketplace:
  enabled: false
```

`src/main.py` initialises the EventBus, PluginManager, marketplace client and exposes management routers (`/api/v1/events`, `/api/v1/plugins`).

## Management Endpoints

- `POST /api/v1/events/reload-config` – reload YAML configuration
- `GET /api/v1/events/plugins` – inspect loaded plugins
- `POST /api/v1/events/plugins/{plugin_name}/enable|disable` – toggle plugins
- `GET /api/v1/plugins/marketplace` – list marketplace plugins
- `POST /api/v1/plugins/install` – install plugin from marketplace or direct URL
- `DELETE /api/v1/plugins/uninstall/{plugin_name}` – uninstall plugin

