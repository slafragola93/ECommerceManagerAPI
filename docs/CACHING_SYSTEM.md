# Sistema di Caching - Documentazione Completa

Questo documento descrive il sistema di caching multi-livello implementato in ECommerceManagerAPI, che utilizza Redis e cache in-memory per migliorare le performance e ridurre il carico sul database.

## Indice

- [Architettura](#architettura)
- [Componenti Principali](#componenti-principali)
- [Decorator @cached](#decorator-cached)
- [Sistema di Invalidazione](#sistema-di-invalidazione)
- [Configurazione](#configurazione)
- [Pattern Avanzati](#pattern-avanzati)
- [Best Practices](#best-practices)
- [Esempi Pratici](#esempi-pratici)
- [Monitoraggio e Statistiche](#monitoraggio-e-statistiche)

---

## Architettura

Il sistema di caching implementa un'architettura **multi-livello (hybrid)** che combina:

### 1. Memory Cache (In-Process)
- **Tecnologia**: `TTLCache` da `cachetools`
- **Caratteristiche**:
  - Cache locale al processo applicativo
  - Accesso ultra-veloce (in-memory)
  - Dimensione massima configurabile (default: 1000 items)
  - TTL configurabile per ogni entry
- **Limiti**: 
  - Non condivisa tra istanze multiple
  - Persa al riavvio del processo

### 2. Redis Cache (Distribuita)
- **Tecnologia**: Redis asincrono (`aioredis`)
- **Caratteristiche**:
  - Cache condivisa tra tutte le istanze dell'applicazione
  - Persistente (sopravvive ai riavvii)
  - Supporta pattern matching per invalidazione
  - Configurabile con pool di connessioni
- **Vantaggi**:
  - Coerenza tra istanze multiple
  - Scalabilità orizzontale

### 3. Modalità Hybrid (Default)
La modalità hybrid combina entrambi i livelli:

```
Richiesta → Memory Cache → Redis Cache → Database
              ↓ (hit)        ↓ (hit)      ↓ (miss)
           Ritorna        Popola Memory  Esegue Query
```

**Comportamento**:
- **Lettura**: Prima controlla memory cache, poi Redis, infine esegue la funzione
- **Scrittura**: Scrive su entrambi i livelli (memory + Redis)
- **Popolamento**: Se trova in Redis, popola anche la memory cache per accessi futuri

---

## Componenti Principali

### CacheManager (`src/core/cache.py`)

Il componente centrale che gestisce tutte le operazioni di cache.

```python
from src.core.cache import get_cache_manager

cache_manager = await get_cache_manager()

# Operazioni base
value = await cache_manager.get("key", layer="auto")
success = await cache_manager.set("key", value, ttl=3600, layer="auto")
await cache_manager.delete("key", layer="auto")
```

**Metodi principali**:
- `get(key, layer)`: Recupera valore dalla cache
- `set(key, value, ttl, preset, layer)`: Salva valore in cache
- `delete(key, layer)`: Elimina chiave dalla cache
- `delete_pattern(pattern, layer)`: Elimina chiavi per pattern
- `get_stats()`: Ottiene statistiche della cache

### Circuit Breaker

Protegge l'applicazione da errori di cache:

- **Stati**: `closed` (normale), `open` (bloccato), `half_open` (ripristino)
- **Soglia errore**: Default 50% (configurabile)
- **Timeout recupero**: Default 5 minuti
- **Comportamento**: Se il circuito è aperto, bypassa la cache ed esegue direttamente

---

## Decorator @cached

Il decorator `@cached` è il modo principale per utilizzare il sistema di caching.

### Uso Base

```python
from src.core.cached import cached

@cached(ttl=3600, key="customer:{customer_id}")
async def get_customer(customer_id: int):
    # Query al database
    return customer
```

### Parametri

| Parametro | Tipo | Descrizione | Default |
|-----------|------|-------------|---------|
| `ttl` | `int` | Time To Live in secondi | `None` (usa default) |
| `preset` | `str` | Nome preset TTL (vedi TTL_PRESETS) | `None` |
| `key` | `str` o `Callable` | Template chiave cache o funzione generatrice | Auto-generata |
| `layer` | `str` | Livello cache: "auto", "memory", "redis", "hybrid" | `"auto"` |
| `stale_ttl` | `int` | TTL per stale-while-revalidate | `None` |
| `single_flight` | `bool` | Previene esecuzioni duplicate concorrenti | `False` |
| `skip_cache` | `bool` | Salta cache per questo call | `False` |
| `tenant_from_user` | `bool` | Estrae tenant dal contesto utente | `True` |

### Esempi di Utilizzo

#### 1. Cache con TTL personalizzato

```python
@cached(ttl=1800)  # 30 minuti
async def get_product_details(product_id: int):
    return product
```

#### 2. Cache con preset TTL

```python
@cached(preset="order", key="order:{tenant}:{order_id}")
async def get_order(tenant: str, order_id: int):
    return order
```

#### 3. Cache con chiave personalizzata

```python
@cached(
    preset="orders_list",
    key="orders:list:{tenant}:{qhash}"
)
async def get_orders_list(tenant: str, filters: dict):
    # qhash viene generato automaticamente dai filtri
    return orders
```

#### 4. Cache solo in memoria

```python
@cached(ttl=60, layer="memory")
async def get_frequently_accessed_data():
    # Dati accessibili molto spesso, solo in memoria
    return data
```

#### 5. Cache solo Redis

```python
@cached(ttl=3600, layer="redis")
async def get_shared_data():
    # Dati condivisi tra istanze, solo Redis
    return data
```

---

## Sistema di Invalidazione

Il sistema supporta diversi metodi di invalidazione della cache.

### 1. Invalidazione Manuale

#### Per entità specifica

```python
from src.core.cached import invalidate_entity

# Invalida tutte le cache relative a un ordine
await invalidate_entity("order", entity_id=123, tenant="tenant1")
```

#### Per pattern

```python
from src.core.cached import invalidate_pattern

# Invalida tutte le liste ordini
await invalidate_pattern("orders:list:*")
```

#### Per utente

```python
from src.core.cached import invalidate_user_data

# Invalida tutte le cache di un utente
await invalidate_user_data(user_id=456)
```

### 2. Invalidazione Automatica (SQLAlchemy Events)

Il sistema si integra con SQLAlchemy per invalidare automaticamente dopo i commit.

#### Funzioni helper

```python
from src.core.invalidation import (
    invalidate_on_create,
    invalidate_on_update,
    invalidate_on_delete
)

# Dopo create
invalidate_on_create(session, "order", tenant="tenant1")

# Dopo update
invalidate_on_update(session, "order", order_id=123, tenant="tenant1")

# Dopo delete
invalidate_on_delete(session, "order", order_id=123, tenant="tenant1")
```

#### Decorator automatico

```python
from src.core.invalidation import auto_invalidate

@auto_invalidate("order", tenant_from_user=True)
async def create_order(order_data: OrderSchema, user: dict):
    # La cache viene invalidata automaticamente dopo il commit
    return order
```

### 3. Context Manager

```python
from src.core.cached import CacheContext

async with CacheContext([
    "orders:list:tenant1:*",
    "order:tenant1:123"
]) as ctx:
    # Operazioni che modificano dati
    update_order(123, new_data)
    # L'invalidazione avviene automaticamente al successo
```

### 4. Invalidazione Post-Commit

Il sistema registra le invalidazioni e le esegue solo dopo commit riusciti:

```python
from src.core.invalidation import get_invalidation_manager

manager = get_invalidation_manager()
manager.add_pending_invalidation(session, "orders:list:*")
# L'invalidazione avverrà solo se il commit ha successo
```

---

## Configurazione

### Variabili d'Ambiente

Tutte le configurazioni sono in `src/core/settings.py` e possono essere sovrascritte via variabili d'ambiente:

```env
# Abilitazione cache
CACHE_ENABLED=true

# Backend cache (redis, memory, hybrid)
CACHE_BACKEND=hybrid

# Configurazione Redis
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=20
REDIS_RETRY_ON_TIMEOUT=true
REDIS_SOCKET_KEEPALIVE=true

# TTL defaults (in secondi)
CACHE_DEFAULT_TTL=300          # 5 minuti
CACHE_STALE_TTL=900            # 15 minuti
CACHE_SHORT_TTL=60             # 1 minuto
CACHE_MEDIUM_TTL=3600          # 1 ora
CACHE_LONG_TTL=86400           # 24 ore

# Memory cache
CACHE_MAX_MEM_ITEMS=1000
CACHE_MAX_VALUE_SIZE=1048576   # 1MB

# Security
CACHE_KEY_SALT=ecommerce-cache-salt

# Circuit breaker
CACHE_ERROR_THRESHOLD=0.5      # 50%
CACHE_RECOVERY_TIMEOUT=300     # 5 minuti

# Feature flags
CACHE_ORDERS_ENABLED=true
CACHE_PRODUCTS_ENABLED=true
CACHE_CUSTOMERS_ENABLED=true
CACHE_EXTERNAL_APIS_ENABLED=true
```

### TTL Presets

I preset TTL sono definiti in `src/core/settings.py`:

```python
TTL_PRESETS = {
    # Static lookup tables (24 ore)
    "order_states": 86400,
    "categories": 86400,
    "brands": 86400,
    "carriers": 86400,
    "countries": 86400,
    
    # Entity details
    "customer": 3600,           # 1 ora
    "product": 21600,           # 6 ore
    "order": 120,               # 2 minuti
    "quote": 300,               # 5 minuti
    "address": 7200,            # 2 ore
    
    # Lists (TTL brevi per dati dinamici)
    "customers_list": 30,       # 30 secondi
    "products_list": 60,        # 1 minuto
    "orders_list": 30,          # 30 secondi
    "quotes_list": 60,          # 1 minuto
    
    # External APIs
    "prestashop_orders": 120,
    "prestashop_customers": 300,
    "fatturapa_invoice": 86400,
}
```

---

## Pattern Avanzati

### 1. Read-Through (Default)

Pattern standard: controlla cache, se miss esegue funzione e salva risultato.

```python
@cached(ttl=3600)
async def get_data():
    # Se in cache → ritorna
    # Se non in cache → esegue funzione → salva → ritorna
    return expensive_operation()
```

### 2. Single-Flight Pattern

Previene esecuzioni duplicate concorrenti della stessa operazione costosa.

```python
@cached(ttl=3600, single_flight=True)
async def expensive_operation(key: str):
    # Se due richieste arrivano simultaneamente con la stessa key,
    # solo una esegue l'operazione, l'altra aspetta il risultato
    return heavy_computation()
```

**Come funziona**:
- Usa lock distribuito (Redis) per sincronizzare tra istanze
- La prima richiesta acquisisce il lock ed esegue
- Le altre attendono e ricevono il risultato dalla cache

### 3. Stale-While-Revalidate

Serve dati "stale" (scaduti) immediatamente mentre aggiorna in background.

```python
@cached(ttl=300, stale_ttl=900)  # Fresh: 5min, Stale: 15min
async def get_dynamic_data():
    return fetch_from_api()
```

**Comportamento**:
- Se dati freschi disponibili → ritorna immediatamente
- Se solo dati stale disponibili → ritorna stale + aggiorna in background
- Se nessun dato → esegue e salva

**Vantaggi**:
- Latenza percepita ridotta
- Dati sempre disponibili (anche se leggermente obsoleti)
- Aggiornamento asincrono

---

## Best Practices

### 1. Scelta del TTL

- **Dati statici** (categorie, brand): TTL lungo (24 ore)
- **Dati semi-statici** (prodotti, clienti): TTL medio (1-6 ore)
- **Dati dinamici** (ordini, liste): TTL breve (30s - 5min)
- **Dati real-time**: No cache o TTL molto breve (< 1 minuto)

### 2. Chiavi Cache

- **Usa template descrittivi**: `"order:{tenant}:{order_id}"`
- **Includi tenant/user** per isolamento dati
- **Usa hash per parametri complessi**: `{qhash}` per filtri

### 3. Invalidazione

- **Invalida sempre dopo modifiche**: Usa `CacheContext` o `auto_invalidate`
- **Invalida liste quando modifichi entità**: `orders:list:*` quando aggiorni un ordine
- **Usa pattern matching**: `orders:*:123` per invalidare tutto relativo a un ordine

### 4. Layer Selection

- **Memory**: Dati accessibili molto spesso, solo per questo processo
- **Redis**: Dati condivisi tra istanze, necessità di coerenza
- **Hybrid (default)**: Miglior performance + coerenza

### 5. Gestione Errori

Il sistema gestisce automaticamente gli errori:
- Circuit breaker protegge da cache down
- Fallback automatico a esecuzione diretta
- Logging degli errori per monitoraggio

---

## Esempi Pratici

### Esempio 1: Repository con Cache

```python
from src.core.cached import cached
from src.repository.cached_order_repository import CachedOrderRepository

class CachedOrderRepository(OrderRepository):
    @cached(preset="order", key="order:{tenant}:{order_id}")
    async def get_by_id_cached(self, tenant: str, order_id: int):
        return self.get_by_id(order_id)
    
    async def update_with_cache_invalidation(
        self, order_id: int, order_data: OrderUpdateSchema, tenant: str
    ):
        from src.core.cached import CacheContext
        
        async with CacheContext([
            f"order:{tenant}:{order_id}",
            f"orders:list:{tenant}:*",
            f"orders:history:{tenant}:{order_id}"
        ]) as ctx:
            # Aggiorna ordine
            success = self.update(order_id, order_data)
            # Cache invalidata automaticamente
            return success
```

### Esempio 2: Service con Cache

```python
from src.core.cached import cached

class ProductService:
    @cached(preset="product", key="product:{product_id}")
    async def get_product(self, product_id: int):
        return self.repository.get_by_id(product_id)
    
    @cached(
        preset="products_list",
        key="products:list:{tenant}:{qhash}",
        single_flight=True  # Previene query duplicate
    )
    async def list_products(self, tenant: str, filters: dict):
        return self.repository.get_all(**filters)
```

### Esempio 3: API Endpoint con Cache

```python
from fastapi import APIRouter
from src.core.cached import cached

router = APIRouter()

@router.get("/orders/{order_id}")
@cached(preset="order", key="order:{tenant}:{order_id}")
async def get_order(order_id: int, tenant: str, user: dict):
    return order_service.get_order(order_id, tenant)
```

### Esempio 4: Invalidazione Automatica

```python
from src.core.invalidation import auto_invalidate

@auto_invalidate("order", tenant_from_user=True)
async def create_order(order_data: OrderSchema, user: dict):
    # Dopo commit riuscito, invalida automaticamente:
    # - order:*:new_id
    # - orders:list:tenant:*
    order = order_repository.create(order_data)
    return order
```

---

## Monitoraggio e Statistiche

### Endpoint di Health Check

```bash
GET /health/cache
```

Risposta:
```json
{
  "status": "healthy",
  "cache_enabled": true,
  "backend": "hybrid",
  "memory_cache": {
    "size": 450,
    "max_size": 1000,
    "ttl": 300
  },
  "redis_cache": {
    "connected_clients": 3,
    "used_memory_human": "12.5MB",
    "keyspace_hits": 1250,
    "keyspace_misses": 89
  },
  "circuit_breaker": {
    "state": "closed",
    "error_rate": 0.02
  }
}
```

### Statistiche Dettagliate

```bash
GET /api/v1/cache/stats
```

### Gestione Cache (Admin)

```bash
# Cancella cache per pattern
DELETE /api/v1/cache?pattern=orders:list:*

# Reset completo (ATTENZIONE!)
POST /api/v1/cache/reset
```

---

## Serializzazione

Il sistema usa `orjson` per serializzazione veloce:

- **Supporta**: datetime, date, SQLAlchemy models, dataclasses, dict, list
- **Performance**: Più veloce di `json` standard
- **Gestione automatica**: Converte automaticamente oggetti complessi

---

## Locks Distribuiti

Per il pattern single-flight, il sistema usa lock distribuiti basati su Redis:

```python
# Internamente usa Redis SET con NX (not exists) e EX (expire)
await redis.set("lock:key", "1", nx=True, ex=60)
```

Questo garantisce che anche in ambiente multi-istanza, solo una istanza esegua l'operazione costosa.

---

## Multi-Tenancy

Il sistema supporta nativamente il multi-tenancy:

- **Isolamento automatico**: Chiavi includono tenant
- **Invalidazione per tenant**: `invalidate_tenant_cache(tenant)`
- **Estrazione automatica**: `tenant_from_user=True` estrae tenant dal contesto

---

## Troubleshooting

### Cache non funziona

1. Verifica `CACHE_ENABLED=true`
2. Controlla connessione Redis: `GET /health/cache`
3. Verifica log per errori

### Cache sempre miss

1. Verifica generazione chiavi (log mostrano le chiavi)
2. Controlla TTL (potrebbe essere troppo breve)
3. Verifica pattern di invalidazione (potrebbe invalidare troppo spesso)

### Performance non migliora

1. Verifica hit rate: `GET /api/v1/cache/stats`
2. Controlla se dati cambiano troppo spesso (TTL troppo lungo)
3. Considera layer "memory" per dati molto accessibili

### Circuit Breaker aperto

1. Verifica errori Redis
2. Controlla `CACHE_ERROR_THRESHOLD`
3. Attendi timeout di recupero o riavvia Redis

---

## Conclusioni

Il sistema di caching implementato offre:

✅ **Performance**: Riduce drasticamente le query al database  
✅ **Scalabilità**: Cache distribuita con Redis  
✅ **Resilienza**: Circuit breaker e fallback automatico  
✅ **Semplicità**: Decorator facile da usare  
✅ **Automaticità**: Invalidazione post-commit integrata  
✅ **Flessibilità**: Pattern configurabili e multi-livello  

Per ulteriori dettagli, consulta il codice sorgente in:
- `src/core/cache.py` - CacheManager
- `src/core/cached.py` - Decorator @cached
- `src/core/invalidation.py` - Sistema di invalidazione
- `src/core/settings.py` - Configurazione

