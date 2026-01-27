# Test Architecture - ECommerceManagerAPI

## Struttura

```
tests/
├── conftest.py              # Fixture principali (app, db, auth, event bus, etc.)
├── unit/                    # Unit test (service, repository, etc.)
├── integration/
│   ├── api/
│   │   └── v1/             # Test endpoint API v1
│   │       ├── test_auth.py
│   │       ├── test_orders.py
│   │       ├── test_shippings_create.py
│   │       ├── test_shippings_multi.py
│   │       ├── test_sync_prestashop.py
│   │       └── test_cache.py
│   └── db/                  # Test integrazione database
├── e2e/                     # Test end-to-end
├── helpers/                 # Helper per test
│   ├── auth.py             # Helper per autenticazione (token, header)
│   └── asserts.py          # Helper per assertion
└── factories/              # Factory per dati di test
    ├── order_factory.py    # Factory per Order e OrderDetail
    └── shipping_factory.py # Factory per Shipping e MultiShipment
```

## Fixture Principali

### Database
- `db_session`: Sessione SQLAlchemy isolata per test (rollback automatico)
- `test_app`: App FastAPI con dependency overrides

### Autenticazione
- `admin_user`, `ordini_user`, `user_user`: Utenti con ruoli diversi
- `admin_client`, `ordini_client`, `user_client`: Client HTTP con utenti preconfigurati

### Event Bus
- `event_bus_spy`: EventBus che registra tutti gli eventi pubblicati

### Carrier
- `fake_carrier_factory`: Factory che ritorna FakeShipmentService

## Uso

### Eseguire tutti i test
```bash
pytest
```

### Eseguire solo test di integrazione
```bash
pytest -m integration
```

### Eseguire solo test unitari
```bash
pytest -m unit
```

### Eseguire solo test e2e
```bash
pytest -m e2e
```

### Eseguire un file specifico
```bash
pytest tests/integration/api/v1/test_orders.py
```

## Pattern di Test

### Arrange-Act-Assert
Tutti i test seguono il pattern AAA:

```python
@pytest.mark.asyncio
async def test_example(self, admin_client, db_session):
    # Arrange: Setup dati di test
    payload = create_simple_order_payload()
    
    # Act: Esegui l'azione
    response = admin_client.post("/api/v1/orders/", json=payload)
    
    # Assert: Verifica risultati
    assert_success_response(response, status_code=201)
    data = response.json()
    assert "id_order" in data
```

## Helper

### Auth Helper (`tests/helpers/auth.py`)
- `create_test_token()`: Crea token JWT per test
- `get_auth_headers()`: Crea header Authorization
- `get_admin_headers()`, `get_ordini_headers()`, `get_user_headers()`: Header preconfigurati

### Assert Helper (`tests/helpers/asserts.py`)
- `assert_success_response()`: Verifica response di successo
- `assert_error_response()`: Verifica response di errore
- `assert_order_status()`: Verifica stato ordine
- `assert_event_published()`: Verifica evento emesso
- `assert_pagination_response()`: Verifica response paginata

## Factory

### Order Factory (`tests/factories/order_factory.py`)
- `create_order_schema()`: Crea OrderSchema completo
- `create_simple_order_payload()`: Crea payload JSON semplice
- `create_order_detail_schema()`: Crea OrderDetailSchema

### Shipping Factory (`tests/factories/shipping_factory.py`)
- `create_multi_shipment_request_schema()`: Crea schema per multi-shipment
- `create_simple_multi_shipment_payload()`: Crea payload JSON semplice

## Note

- I test usano SQLite in-memory per isolamento completo
- Le chiamate HTTP esterne (carrier, PrestaShop) sono mockate
- Il background task polling è disabilitato nei test
- La cache usa solo memory backend (no Redis)

## TODO

Alcuni test sono skeleton e richiedono setup database completo:
- Creazione utenti per test auth
- Creazione ordini per test orders
- Creazione store per test sync PrestaShop
- Setup completo multi-shipment per test spedizioni
