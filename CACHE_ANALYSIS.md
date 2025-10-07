# ECommerceManagerAPI - Analisi Hot Path per Caching

## Architettura Attuale

### Stack Tecnologico
- **FastAPI** 0.110.1 + Python 3.11+
- **SQLAlchemy** 2.0.29 ORM con MySQL (PyMySQL)
- **Redis** 6.4.0 (già presente ma limitato)
- **JWT** autenticazione con ruoli/permessi
- **Pytest** per testing

### Struttura Progetto
```
src/
├── main.py                    # Entry point FastAPI
├── database.py               # Configurazione DB
├── routers/                  # Endpoint API
│   ├── order.py             # HOT PATH - Gestione ordini
│   ├── customer.py          # HOT PATH - Anagrafica clienti  
│   ├── product.py           # HOT PATH - Catalogo prodotti
│   ├── preventivi.py        # HOT PATH - Preventivi
│   ├── order_state.py       # HOT PATH - Stati ordine
│   └── sync.py              # HOT PATH - Sincronizzazione
├── repository/              # Layer accesso dati
│   ├── order_repository.py  # HOT PATH - Query complesse
│   ├── customer_repository.py
│   ├── product_repository.py
│   └── preventivo_repository.py
├── services/                # Logica business
│   ├── ecommerce/
│   │   └── prestashop_service.py  # HOT PATH - API esterne
│   ├── fatturapa_service.py       # HOT PATH - API esterne
│   └── preventivo_service.py
└── models/                  # Modelli SQLAlchemy
```

## Hot Path Identificati

### 1. Endpoint più utilizzati (per frequenza)
1. **GET /api/v1/orders/** - Lista ordini con filtri/paginazione
2. **GET /api/v1/orders/{id}** - Dettaglio ordine completo
3. **GET /api/v1/customers/** - Lista clienti
4. **GET /api/v1/products/** - Catalogo prodotti
5. **GET /api/v1/preventivi/** - Lista preventivi
6. **GET /api/v1/order_states** - Stati ordine (lookup table)
7. **GET /api/v1/categories** - Categorie prodotti
8. **GET /api/v1/brands** - Brand prodotti

### 2. Query più costose (per complessità)
1. **OrderRepository.get_all()** - JOIN multipli + filtri + paginazione
2. **ProductRepository.get_all()** - JOIN Brand + Category + filtri
3. **CustomerRepository.get_all()** - JOIN Address + filtri
4. **PrestaShopService.sync_orders()** - API esterne + bulk insert
5. **FatturaPAService.get_pool()** - API esterne + parsing XML
6. **OrderRepository.formatted_output()** - Relazioni lazy loading

### 3. Operazioni esterne costose
1. **PrestaShop API** - Sincronizzazione ordini/clienti/prodotti
2. **FatturaPA API** - Download pool fatture elettroniche
3. **Carrier API** - Tracking spedizioni

## Analisi Performance Attuale

### Problemi identificati:
1. **N+1 Query Problem**: `formatted_output()` carica relazioni lazy
2. **Query ripetitive**: Stati ordine, categorie, brand richiesti spesso
3. **API esterne**: Nessuna cache per PrestaShop/FatturaPA
4. **Paginazione**: Count query separate per ogni lista
5. **Filtri complessi**: Query rebuild per ogni parametro

### Opportunità di caching:
1. **Lookup tables**: order_states, categories, brands (24h TTL)
2. **Dettagli entità**: order/{id}, customer/{id}, product/{id} (1-6h TTL)
3. **Liste filtrate**: orders:list, products:list (30-60s TTL)
4. **API esterne**: prestashop:*, fatturapa:* (60-120s TTL)
5. **Metadati**: configurazioni, settings (15m TTL)

## Configurazione Attuale Cache

Il progetto ha già `fastapi-cache2` configurato ma limitato:
```python
# main.py - Configurazione attuale
if REDIS_AVAILABLE:
    redis = aioredis.from_url("redis://localhost")
    FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
```

**Limiti attuali:**
- Cache solo in-memory o Redis semplice
- Nessuna strategia TTL differenziata
- Nessuna invalidazione intelligente
- Nessun supporto per stale-while-revalidate
- Nessuna metrica/telemetria

## Raccomandazioni per Implementazione

### Priorità 1 (Impatto alto, Complessità bassa)
1. Cache lookup tables (order_states, categories, brands)
2. Cache dettagli entità singole
3. Middleware ETag per conditional GET

### Priorità 2 (Impatto alto, Complessità media)
1. Cache liste con filtri (con query hash)
2. Cache API PrestaShop/FatturaPA
3. Invalidazione on-write

### Priorità 3 (Impatto medio, Complessità alta)
1. Stale-while-revalidate
2. Single-flight pattern
3. Metriche avanzate

### Pattern di invalidazione necessari:
- **Order CRUD** → invalidate order:*, orders:list:*
- **Customer CRUD** → invalidate customer:*, customers:list:*
- **Product CRUD** → invalidate product:*, products:list:*
- **Order State Change** → invalidate order:{id}, orders:history:{id}
- **PrestaShop Sync** → invalidate prestashop:*
