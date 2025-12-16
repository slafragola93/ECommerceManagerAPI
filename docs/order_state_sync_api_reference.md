# API Reference: Order State Synchronization System

## 🏗️ Architecture Overview

The Order State Synchronization system is an event-driven architecture that maintains bidirectional state consistency between the local ECommerceManagerAPI and external e-commerce platforms (PrestaShop, Shopify, etc.).

### Key Components

```
┌─────────────────────────────────────────────────────────────────┐
│                     ORDER STATE FLOW                            │
└─────────────────────────────────────────────────────────────────┘

 [API Endpoint]
      ↓
 [Order Service] → emit ORDER_STATUS_CHANGED event
      ↓
 [EventBus] → routes to registered handlers
      ↓
 [PlatformStateSyncHandler]
      ↓
      ├─→ Query platform_state_triggers
      ├─→ Match local state → platform state
      ├─→ Query ecommerce_order_states for platform ID
      └─→ Call EcommerceService.sync_order_state_to_platform()
           ↓
      [PrestaShopService] POST /api/order_histories
           ↓
      Update order.id_ecommerce_state
```

---

## 📚 Database Schema

### Table: `ecommerce_order_states`

Stores synchronized order states from e-commerce platforms.

| Column | Type | Description |
|--------|------|-------------|
| `id_ecommerce_order_state` | INT (PK) | Local unique ID |
| `id_store` | INT (FK) | Reference to stores |
| `id_platform_state` | INT | State ID on the platform (e.g., PrestaShop state ID) |
| `name` | VARCHAR(200) | State name from platform |
| `platform_name` | VARCHAR(50) | Platform name (PrestaShop, Shopify, etc.) |
| `date_add` | DATETIME | Creation timestamp |
| `updated_at` | DATETIME | Last update timestamp |

**Indexes:**
- Primary: `id_ecommerce_order_state`
- Foreign Key: `id_store` → `stores.id_store`

---

### Table: `platform_state_triggers`

Defines mapping rules between local states and platform states.

| Column | Type | Description |
|--------|------|-------------|
| `id_trigger` | INT (PK) | Trigger unique ID |
| `event_type` | VARCHAR(100) | Event type: `order_status_changed` or `shipping_status_changed` |
| `id_store` | INT (FK) | Store ID |
| `state_type` | VARCHAR(20) | State type: `order_state` or `shipping_state` |
| `id_state_local` | INT | Local state ID (OrderState.id_order_state) |
| `id_state_platform` | INT (FK) | Reference to ecommerce_order_states.id_ecommerce_order_state |
| `is_active` | BOOLEAN | Whether the trigger is active |
| `created_at` | DATETIME | Creation timestamp |
| `updated_at` | DATETIME | Last update timestamp |

**Indexes:**
- Primary: `id_trigger`
- Foreign Keys:
  - `id_store` → `stores.id_store`
  - `id_state_platform` → `ecommerce_order_states.id_ecommerce_order_state`
- Indexed: `event_type`, `is_active`

---

### Table: `orders` (Updated)

Added column for tracking current e-commerce state.

| New Column | Type | Description |
|------------|------|-------------|
| `id_ecommerce_state` | INT (FK, nullable) | Current state on e-commerce platform |

**Relationship:**
- Foreign Key: `id_ecommerce_state` → `ecommerce_order_states.id_ecommerce_order_state`

---

## 🔌 API Endpoints

### 1. Get Initialization Data

Retrieves all initialization data including synchronized e-commerce states.

**Request:**
```http
GET /api/v1/init
```

**Response:**
```json
{
  "platforms": [...],
  "languages": [...],
  "countries": [...],
  "order_states": [...],
  "ecommerce_order_states": [
    {
      "id_platform_state": 1,
      "id_store": 1,
      "name": "Contanti alla consegna"
    },
    {
      "id_platform_state": 3,
      "id_store": 1,
      "name": "03 - Preparazione ordine in corso...."
    },
    {
      "id_platform_state": 4,
      "id_store": 1,
      "name": "05 - Spedito"
    }
  ],
  "cache_info": {...}
}
```

---

### 2. Get Orders (with E-commerce State)

Retrieves orders with their current e-commerce state.

**Request:**
```http
GET /api/v1/orders?page=1&limit=20
```

**Response:**
```json
{
  "orders": [
    {
      "id_order": 32,
      "reference": "ABCD1234",
      "id_order_state": 3,
      "ecommerce_order_state": {
        "id": 3,
        "state_name": "03 - Preparazione ordine in corso...."
      },
      "total_price_with_tax": 150.00,
      ...
    }
  ],
  "total": 100,
  "page": 1,
  "limit": 20
}
```

**Note:** `ecommerce_order_state` will be `null` if no platform state is assigned.

---

### 3. Get Single Order

**Request:**
```http
GET /api/v1/orders/{order_id}
```

**Response:**
```json
{
  "id_order": 32,
  "reference": "ABCD1234",
  "id_order_state": 3,
  "ecommerce_order_state": {
    "id": 3,
    "state_name": "03 - Preparazione ordine in corso...."
  },
  "customer": {...},
  "address_delivery": {...},
  "order_details": [...],
  ...
}
```

---

### 4. Update Order Status

Updates order status and triggers automatic platform synchronization.

**Request:**
```http
PUT /api/v1/orders/{order_id}/status
Content-Type: application/json

{
  "id_order_state": 3
}
```

**Response:**
```json
{
  "message": "Stato ordine aggiornato con successo",
  "id_order": 32,
  "old_state": 1,
  "new_state": 3
}
```

**Side Effects:**
1. Emits `ORDER_STATUS_CHANGED` event
2. `PlatformStateSyncHandler` checks for matching trigger
3. If trigger found → calls PrestaShop API
4. Updates `order.id_ecommerce_state`

---

### 5. Bulk Update Order Status

Updates multiple orders at once.

**Request:**
```http
POST /api/v1/orders/bulk-status
Content-Type: application/json

{
  "orders": [
    {"id_order": 32, "id_order_state": 3},
    {"id_order": 33, "id_order_state": 3}
  ]
}
```

**Response:**
```json
{
  "successful": [
    {"id_order": 32, "old_state": 1, "new_state": 3},
    {"id_order": 33, "old_state": 1, "new_state": 3}
  ],
  "failed": [],
  "summary": {
    "total": 2,
    "successful_count": 2,
    "failed_count": 0
  }
}
```

---

## 🎯 Event System

### Event: `ORDER_STATUS_CHANGED`

**Emitted when:** Order state changes via API

**Event Data:**
```python
{
    "order_id": 32,
    "old_state_id": 1,
    "new_state_id": 3,
    "id_platform": 1
}
```

**Handlers:**
- `PlatformStateSyncHandler` (priority: synchronizes with e-commerce platform)
- `StockAutoUpdateHandler` (may adjust stock based on state)

---

## 🔧 Service Layer

### `PrestaShopService.sync_order_state_to_platform()`

Synchronizes order state to PrestaShop via XML API.

**Method Signature:**
```python
async def sync_order_state_to_platform(
    self, 
    order_id: int, 
    platform_state_id: int
) -> bool
```

**Parameters:**
- `order_id`: Local order ID
- `platform_state_id`: PrestaShop state ID (from `ecommerce_order_states.id_platform_state`)

**Returns:**
- `True` if synchronization successful
- `False` if failed

**Implementation:**
```python
# 1. Retrieve order.id_origin (PrestaShop order ID)
# 2. Build XML payload:
<?xml version="1.0" encoding="UTF-8"?>
<prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
  <order_history>
    <id_order>{id_origin}</id_order>
    <id_order_state>{platform_state_id}</id_order_state>
  </order_history>
</prestashop>

# 3. POST to PrestaShop /api/order_histories
# 4. Retry with exponential backoff (3 attempts)
```

**Retry Strategy:**
- Attempts: 3
- Backoff: 1s, 2s, 4s
- Uses Tenacity `@retry` decorator

---

## 🔄 Background Tasks

### Periodic State Synchronization

**Task:** `run_order_states_sync_task()`

**Frequency:** Every hour

**Purpose:** Sync all order states from e-commerce platforms

**Flow:**
```python
1. Retrieve all active stores
2. For each store:
   a. Get ecommerce service (PrestaShop, Shopify, etc.)
   b. Call service.sync_order_states()
   c. Query platform states from API
   d. Update/create records in ecommerce_order_states table
3. Commit changes
4. Wait 1 hour
5. Repeat
```

**Endpoint to manually trigger (alternative):**
```http
POST /api/v1/sync/prestashop?store_id=1
```

---

## 🔐 Configuration

### Enable/Disable Handler

Edit `config/event_handlers.yaml`:

```yaml
plugins:
  platform_state_sync:
    enabled: true  # Set to false to disable
```

### Create Trigger

**SQL:**
```sql
INSERT INTO platform_state_triggers 
  (event_type, id_store, state_type, id_state_local, id_state_platform, is_active)
VALUES 
  ('order_status_changed', 1, 'order_state', 3, 3, 1);
```

**Python:**
```python
from src.models.platform_state_trigger import PlatformStateTrigger

trigger = PlatformStateTrigger(
    event_type='order_status_changed',
    id_store=1,
    state_type='order_state',
    id_state_local=3,
    id_state_platform=3,  # FK to ecommerce_order_states
    is_active=True
)
db.add(trigger)
db.commit()
```

---

## 🧪 Testing

### Unit Test Example

```python
import pytest
from src.events.plugins.platform_state_sync.handlers import PlatformStateSyncHandler
from src.events.core.event import Event, EventType

@pytest.mark.asyncio
async def test_order_state_sync():
    handler = PlatformStateSyncHandler()
    
    event = Event(
        event_type=EventType.ORDER_STATUS_CHANGED.value,
        data={
            'order_id': 32,
            'old_state_id': 1,
            'new_state_id': 3,
            'id_platform': 1
        }
    )
    
    # Should handle the event
    assert handler.can_handle(event) is True
    
    # Execute handler
    await handler.handle(event)
    
    # Verify order.id_ecommerce_state was updated
    order = db.query(Order).filter(Order.id_order == 32).first()
    assert order.id_ecommerce_state == 3
```

---

## 📊 Performance Considerations

### Database Queries

- **Eager Loading**: Use `joinedload(Order.ecommerce_order_state)` to avoid N+1 queries
- **Indexes**: All foreign keys and event_type columns are indexed

### API Calls

- **Retry Logic**: 3 attempts with exponential backoff
- **Timeout**: 30 seconds total, 10 seconds for connection
- **Async**: All external calls use aiohttp for non-blocking I/O

### Caching

- Init endpoint caches `ecommerce_order_states` for 1 day
- Cache invalidation on sync

---

## 🐛 Debugging

### Enable Debug Logging

```python
import logging
logging.getLogger('src.events.plugins.platform_state_sync').setLevel(logging.DEBUG)
```

### Log Messages

**Trigger not found:**
```
DEBUG - Nessun trigger trovato per order_id=32, state_id=3, store=1
```

**Successful sync:**
```
INFO - Stato ordine 32 sincronizzato con successo a store 1 (platform_state_id=3)
INFO - Updated order 32.id_ecommerce_state to 3
```

**Sync failed:**
```
ERROR - Errore sync order state per order_id=32: HTTP 401 Unauthorized
```

---

## 🔮 Future Enhancements

- [ ] CRUD endpoints for `platform_state_triggers`
- [ ] Webhook support for platform → local sync
- [ ] Support for Shopify, WooCommerce
- [ ] State transition validation rules
- [ ] Admin dashboard for trigger management
- [ ] Batch state updates optimization

---

## 📞 Developer Support

For technical questions:
- Check logs in `src/events/plugins/platform_state_sync/handlers.py`
- Review event emission in `src/services/routers/order_service.py`
- Verify trigger configuration in database
- Consult PrestaShop API docs: https://devdocs.prestashop.com/

