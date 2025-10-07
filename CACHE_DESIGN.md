# Design Sistema Caching Multilivello

## Architettura Cache

### Strati di Cache

#### 1. In-Memory Cache (L1)
- **Backend**: `cachetools.TTLCache` (LRU + TTL)
- **Scope**: Per processo FastAPI
- **Use case**: Metadati piccoli, lookup tables
- **TTL**: 5-60 minuti
- **Max items**: 1000-5000 (configurabile)

#### 2. Redis Cache (L2) 
- **Backend**: `redis.asyncio` 
- **Scope**: Cluster multi-istanza
- **Use case**: Query results, API responses, deduplication
- **TTL**: 1 minuto - 24 ore
- **Features**: Pub/Sub, Locks, SWR

#### 3. Application Cache (L3)
- **Backend**: Decorator + Service layer
- **Scope**: Business logic
- **Use case**: Computed values, aggregated data
- **TTL**: Variabile per business logic

## Schema Chiavi e TTL

### Lookup Tables (Static/Rare)
```
order_states:{tenant}                    → 24h
categories:{tenant}                      → 24h  
brands:{tenant}                          → 24h
carriers:{tenant}                        → 24h
countries:{tenant}                       → 24h
langs:{tenant}                           → 24h
config:{tenant}:{key}                    → 15m
```

### Entità Singole
```
customer:{tenant}:{id}                   → 1h
product:{tenant}:{id}                    → 6h
order:{tenant}:{id}                      → 2m
quote:{tenant}:{id}                      → 5m
address:{tenant}:{id}                    → 2h
```

### Liste e Query
```
customers:list:{tenant}:{qhash}          → 30s
products:list:{tenant}:{qhash}           → 1m
orders:list:{tenant}:{qhash}             → 30s
quotes:list:{tenant}:{qhash}             → 1m
orders:history:{tenant}:{order_id}       → 5m
```

### API Esterne
```
prestashop:orders:{shop_id}:{page}:{hash} → 2m
prestashop:customers:{shop_id}:{page}    → 5m
prestashop:products:{shop_id}:{page}     → 10m
fatturapa:pool:{tenant}:{page_token}     → 1m
fatturapa:inv:{sdi}:meta                 → 24h
```

### Locks e Deduplication
```
lock:prestashop:sync:{shop_id}           → 60s
lock:fatturapa:download:{sdi}            → 60s
lock:order:process:{order_id}            → 30s
```

## Pattern di Caching

### 1. Read-Through
```python
@cached(ttl=3600, key="customer:{tenant}:{customer_id}")
async def get_customer(customer_id: int, tenant: str):
    return await customer_repo.get_by_id(customer_id)
```

### 2. Stale-While-Revalidate (SWR)
```python
@cached(ttl=60, stale_ttl=300, key="orders:list:{tenant}:{qhash}")
async def get_orders_list(tenant: str, filters: dict):
    # Serve stale se presente, aggiorna in background
    pass
```

### 3. Single-Flight
```python
@cached(ttl=120, single_flight=True, key="prestashop:orders:{shop_id}")
async def fetch_prestashop_orders(shop_id: str):
    # Solo una richiesta per processo/cluster
    pass
```

### 4. Conditional GET (ETag)
```python
# Middleware automatico per endpoint GET
# Calcola ETag da updated_at o hash response
# Ritorna 304 se If-None-Match matcha
```

## Invalidazione

### Event-Driven Invalidation
```python
# Post-commit hooks
@invalidate_on_commit
def create_order(order_data):
    # Auto-invalidate: order:*, orders:list:*
    pass

@invalidate_on_commit  
def update_customer(customer_id, data):
    # Auto-invalidate: customer:{id}, customers:list:*
    pass
```

### Manual Invalidation
```python
# Pattern-based invalidation
cache.invalidate_pattern("order:*")           # Tutti gli ordini
cache.invalidate_pattern("orders:list:*")     # Tutte le liste ordini
cache.invalidate_pattern("prestashop:*")      # Tutte le cache PrestaShop
```

### Cross-Service Invalidation
```python
# Pub/Sub per multi-istanza
cache.publish_invalidation("order:123")       # Invalida su tutte le istanze
```

## Sicurezza e Isolamento

### Tenant Isolation
```python
# Tutte le chiavi includono tenant
key = f"order:{tenant}:{order_id}"
```

### User Context (quando necessario)
```python
# Per dati user-specific
key = f"user_orders:{tenant}:{user_id}:{qhash}"
```

### Sensitive Data Protection
```python
# Non cache-are mai:
# - Token JWT
# - Password hash
# - Dati PII sensibili
# - Risposte con errori 4xx/5xx
```

## Configurazione

### Environment Variables
```bash
# Cache abilitazione
CACHE_ENABLED=true
CACHE_BACKEND=redis  # redis, memory, hybrid

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=20
REDIS_RETRY_ON_TIMEOUT=true

# TTL Defaults
CACHE_DEFAULT_TTL=300
CACHE_STALE_TTL=900
CACHE_MAX_MEM_ITEMS=1000

# Security
CACHE_KEY_SALT=your-secret-salt
CACHE_MAX_VALUE_SIZE=1048576  # 1MB

# Metrics
CACHE_METRICS_ENABLED=true
CACHE_LOG_LEVEL=INFO
```

### Feature Flags
```python
# Per rollout graduale
CACHE_ORDERS_ENABLED=true
CACHE_PRODUCTS_ENABLED=true
CACHE_CUSTOMERS_ENABLED=false  # Disabilitato per testing
CACHE_EXTERNAL_APIS_ENABLED=true
```

## Metriche e Monitoring

### Cache Metrics
```python
# Prometheus metrics
cache_hit_total{cache_layer, key_pattern}
cache_miss_total{cache_layer, key_pattern}  
cache_latency_seconds{cache_layer, operation}
cache_size_bytes{cache_layer}
cache_eviction_total{cache_layer, reason}
```

### Logging
```python
# Structured logging
{
  "event": "cache_hit",
  "key": "order:tenant1:123", 
  "layer": "redis",
  "ttl_remaining": 1800,
  "correlation_id": "req-123"
}
```

## Resilienza e Fallback

### Graceful Degradation
```python
# Se Redis down → fallback a in-memory
# Se cache miss → serve direttamente dal DB
# Se stale data → serve stale + refresh background
```

### Circuit Breaker
```python
# Se cache error rate > 50% → bypass cache temporaneamente
# Auto-recovery dopo 5 minuti
```

### Health Checks
```python
GET /health/cache
{
  "redis": "healthy",
  "memory": "healthy", 
  "hit_rate": 0.85,
  "avg_latency_ms": 2.3
}
```
