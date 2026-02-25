# Documentazione completa – ECommerceManagerAPI

API REST per la gestione di ordini, resi, documenti fiscali, spedizioni e sincronizzazione con e-commerce (PrestaShop e altri). Il progetto espone il titolo **"Elettronew API"** in runtime.

---

## Indice

1. [Panoramica](#1-panoramica)
2. [Stack tecnologico](#2-stack-tecnologico)
3. [Struttura del progetto](#3-struttura-del-progetto)
4. [Requisiti e installazione](#4-requisiti-e-installazione)
5. [Configurazione](#5-configurazione)
6. [Database e migrazioni](#6-database-e-migrazioni)
7. [Architettura applicativa](#7-architettura-applicativa)
8. [API e router](#8-api-e-router)
9. [Autenticazione e autorizzazione](#9-autenticazione-e-autorizzazione)
10. [Funzionalità principali](#10-funzionalità-principali)
11. [Sistema eventi e plugin](#11-sistema-eventi-e-plugin)
12. [Cache](#12-cache)
13. [Gestione errori](#13-gestione-errori)
14. [Testing e riferimenti](#14-testing-e-riferimenti)

---

## 1. Panoramica

- **Nome applicazione**: Elettronew API (ECommerceManagerAPI).
- **Scopo**: centralizzare la gestione di ordini, clienti, prodotti, spedizioni, documenti fiscali (fatture, note di credito, resi) e sincronizzazione con piattaforme e-commerce (es. PrestaShop).
- **Tipo**: API REST basata su **FastAPI**, con persistenza **MySQL** e uso di **SQLAlchemy** come ORM.

---

## 2. Stack tecnologico

| Area | Tecnologia |
|------|------------|
| Framework | FastAPI 0.110.x |
| Linguaggio | Python 3.x |
| ORM / DB | SQLAlchemy 2.x, PyMySQL |
| Database | MySQL |
| Validazione / DTO | Pydantic 2.x |
| Migrazioni | Alembic |
| Server ASGI | Uvicorn |
| Cache | Redis (opzionale), cache in-memory / hybrid |
| Auth | JWT (python-jose), bcrypt |
| PDF | fpdf2, pypdf |
| HTTP client | httpx, requests, aiohttp |
| Altro | pandas, python-dotenv, tenacity, pendulum |

---

## 3. Struttura del progetto

```
ECommerceManagerAPI/
├── alembic/                    # Migrazioni database
│   └── versions/
├── config/                     # Configurazione (es. event_handlers.yaml)
├── docs/                       # Documentazione aggiuntiva
├── media/                      # File statici serviti dall’API
├── scripts/                    # Script di setup (init, sync, ecc.)
├── src/
│   ├── main.py                 # Punto di ingresso FastAPI, lifespan, middleware, router
│   ├── database.py             # Engine e sessione SQLAlchemy, get_db
│   ├── core/                   # Eccezioni, cache, container DI, settings, monitoring
│   ├── events/                 # Event bus, plugin loader, handler di evento
│   ├── factories/              # Factory per servizi (es. carrier)
│   ├── middleware/             # Logging, performance, security, conditional cache
│   ├── models/                 # Modelli SQLAlchemy (Order, Customer, FiscalDocument, ecc.)
│   ├── repository/            # Layer di accesso dati (interfacce + implementazioni)
│   ├── routers/                # Endpoint API (order, customer, shipments, fiscal_documents, ecc.)
│   ├── schemas/                # Modelli Pydantic per request/response
│   └── services/               # Business logic (routers, ecommerce, pdf, external, sync)
├── tests/
├── .env                        # Variabili d’ambiente (non in repo)
├── requirements.txt
├── README.md
├── SETUP_INIZIALE.md           # Setup iniziale (se presente)
└── DOCUMENTAZIONE.md           # Questo file
```

---

## 4. Requisiti e installazione

### Requisiti

- Python 3.10+
- MySQL
- (Opzionale) Redis per cache

### Installazione

```bash
# Clone e virtualenv
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# Dipendenze
pip install -r requirements.txt
```

### Setup iniziale (primo avvio)

```bash
# Setup automatico (consigliato)
python scripts/setup_initial.py

# Oppure manuale
python scripts/init_app_configurations.py
python scripts/init_order_states.py
python scripts/init_prestashop_platform.py
```

### Avvio server

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

- **Swagger UI**: `http://localhost:8000/docs`
- **Health**: `http://localhost:8000/api/v1/health` (se esposto)

---

## 5. Configurazione

La configurazione dipende da variabili d’ambiente (es. `.env`).

### Database (obbligatorio)

| Variabile | Descrizione |
|-----------|-------------|
| `DATABASE_MAIN_USER` | Utente MySQL |
| `DATABASE_MAIN_PASSWORD` | Password MySQL |
| `DATABASE_MAIN_ADDRESS` | Host (es. localhost) |
| `DATABASE_MAIN_PORT` | Porta (es. 3306) |
| `DATABASE_MAIN_NAME` | Nome database |

URL usato in `src/database.py`:

`mysql+pymysql://{user}:{password}@{address}:{port}/{name}`

### Cache

| Variabile | Descrizione |
|-----------|-------------|
| `CACHE_ENABLED` | Abilita cache (default: true) |
| `CACHE_BACKEND` | redis, memory, hybrid |
| `REDIS_URL` | Es. redis://localhost:6379/0 |

### Background tasks

| Variabile | Descrizione |
|-----------|-------------|
| `TRACKING_POLLING_ENABLED` | Abilita polling tracking (default: true) |

### Corrieri / integrazioni

In `src/core/settings.py` (o env) sono definibili URL e chiavi per DHL, BRT, FedEx, ecc. (es. `DHL_BASE_URL_PROD`, `BRT_BASE_URL_PROD`).

---

## 6. Database e migrazioni

- **ORM**: SQLAlchemy 2.x con modelli in `src/models/`.
- **Migrazioni**: Alembic in `alembic/versions/`.

Comandi utili:

```bash
# Crea una nuova revisione (dopo aver modificato i modelli)
alembic revision --autogenerate -m "descrizione"

# Applica tutte le migrazioni
alembic upgrade head

# Rollback di un passo
alembic downgrade -1
```

Le migrazioni toccano tabelle come `orders`, `order_details`, `fiscal_documents`, `fiscal_document_details`, `customers`, `products`, `shipments`, ecc.

---

## 7. Architettura applicativa

Flusso tipico delle richieste:

1. **Router** (`src/routers/`): riceve la richiesta HTTP, validazione input (Pydantic), chiama il **service**.
2. **Service** (`src/services/routers/`, `src/services/ecommerce/`, ecc.): logica di business, orchestrazione, chiamate a **repository** e servizi esterni.
3. **Repository** (`src/repository/`): accesso al database (query, create, update, delete) tramite **modelli** SQLAlchemy.
4. **Models** (`src/models/`): entità DB.
5. **Schemas** (`src/schemas/`): DTO in ingresso/uscita (validazione e serializzazione).

Il **container di dependency injection** (`src/core/container_config.py`) registra interfacce e implementazioni (repository, servizi) e risolve le dipendenze (anche con sessione DB dove serve).

---

## 8. API e router

Prefisso base: **`/api/v1`**. Tutti i router sono montati senza ulteriore prefisso globale (il prefisso è su ogni router).

| Router | Prefisso | Contenuto principale |
|--------|----------|----------------------|
| auth | `/api/v1/auth` | Login, token JWT |
| user | (da verificare in `user.py`) | Utenti |
| role | (da verificare) | Ruoli |
| app_configuration | (da verificare) | Configurazioni app |
| lang | (da verificare) | Lingue |
| customer | `/api/v1/customers` | Clienti |
| category | (da verificare) | Categorie |
| brand | (da verificare) | Brand |
| product | `/api/v1/products` | Prodotti |
| shipping_state | (da verificare) | Stati spedizione |
| country | (da verificare) | Paesi |
| address | `/api/v1/addresses` | Indirizzi |
| **order** | **`/api/v1/orders`** | Ordini, resi (create return, get return by id, lista resi) |
| carrier | `/api/v1/carriers` | Corrieri |
| api_carrier | `/api/v1/api_carriers` | API corrieri |
| carrier_assignment | `/api/v1/carrier-assignments` | Assegnazioni corrieri |
| platform | (da verificare) | Piattaforme |
| store | `/api/v1/stores` | Negozi |
| sectional | (da verificare) | Sezionali |
| message | (da verificare) | Messaggi |
| payment | (da verificare) | Pagamenti |
| tax | (da verificare) | Tasse |
| order_state | `/api/v1/order-states` | Stati ordine |
| shipping | `/api/v1/shippings` | Spedizioni (logica shipping) |
| order_package | `/api/v1/order_packages` | Pacchi ordine |
| sync | `/api/v1/sync` | Sincronizzazione |
| preventivi | `/api/v1/preventivi` | Preventivi |
| ddt | `/api/v1/ddt` | DDT |
| **fiscal_documents** | **`/api/v1/fiscal_documents`** | Documenti fiscali (fatture, note di credito) |
| platform_state_trigger | `/api/v1/platform-state-triggers` | Trigger stati piattaforma |
| init | `/api/v1/init` | Inizializzazione |
| carriers_configuration | (da verificare) | Configurazione corrieri |
| **shipments** | **`/api/v1/shippings`** (tag Shipments) | Spedizioni (gestione pratica) |
| events | `/api/v1/events` | Sistema eventi |
| csv_import | `/api/v1/sync/import` | Import CSV |

Esempi di endpoint rilevanti:

- Ordini: `GET/POST /api/v1/orders`, `GET /api/v1/orders/{id}`.
- Resi: `POST /api/v1/orders/returns` (crea reso), `GET /api/v1/orders/{id_order}/returns`, `GET /api/v1/orders/returns/get-return-by-id/{id_fiscal_document}`, `PUT /api/v1/orders/returns/{id_fiscal_document}`.
- Documenti fiscali: sotto ` /api/v1/fiscal_documents` (fatture, note di credito, lista, dettaglio).
- Spedizioni: sotto ` /api/v1/shippings` (shipments).

La documentazione interattiva completa è in **`/docs`** (Swagger UI).

---

## 9. Autenticazione e autorizzazione

- **JWT**: token rilasciato tramite endpoint sotto `/api/v1/auth` (login). Le route protette richiedono il token (es. header `Authorization: Bearer <token>`).
- **Ruoli e permessi**: decorator/pattern tipo `@authorize(roles_permitted=[...], permissions_required=['R','C','U','D'])` e `@check_authentication` sono usati sui router per controllare accesso per ruolo e permesso.
- Le eccezioni `AuthenticationException` e `AuthorizationException` sono mappate in 401 e 403 con formato standard (vedi Gestione errori).

---

## 10. Funzionalità principali

### Ordini

- CRUD ordini, filtri, paginazione.
- Stati ordine e sincronizzazione con e-commerce (PrestaShop).
- Package ordine (order_packages).

### Resi (returns)

- Creazione reso per ordine: articoli da restituire, spese di spedizione, note.
- Validazione quantità (rispetto a quantità già resa).
- Flag `is_partial`: impostato a `True` (1) quando **ogni** prodotto dell’ordine è stato interamente reso (reso completo).
- Dettaglio reso: documento con customer, indirizzi, payment, shipping e righe dettaglio (incl. campo `rda` da order detail).

### Documenti fiscali

- **Fatture** (invoice): creazione da ordine, numerazione, totale.
- **Note di credito** (credit_note): da fattura, totali o parziali, con/senza spese spedizione.
- **Resi** (return): documenti tipo “return” con dettagli riga (product_qty, prezzi, rda, ecc.).
- Modelli: `FiscalDocument`, `FiscalDocumentDetail`. Repository e service dedicati; risposte formattate con schemi Pydantic (es. `ReturnResponseSchema`, `ReturnDetailResponseSchema`).

### Spedizioni

- Gestione spedizioni (shipments), stati, tracking.
- Integrazioni con corrieri (BRT, DHL, FedEx) tramite servizi dedicati e factory.
- Polling tracking in background (opzionale, `TRACKING_POLLING_ENABLED`).

### Sincronizzazione e-commerce

- Sincronizzazione con PrestaShop (ordini, stati, ecc.).
- Sync stati ordine in background (periodico).
- Documentazione: `docs/ECOMMERCE_SYNC.md`.

### Preventivi e DDT

- Moduli preventivi (`/api/v1/preventivi`) e DDT (`/api/v1/ddt`) con relativi servizi e PDF.

### Import

- Import CSV sotto `/api/v1/sync/import`.

---

## 11. Sistema eventi e plugin

- **Event bus**: pubblicazione/sottoscrizione eventi (es. ordine creato, stato cambiato).
- **Plugin**: caricamento da directory (es. `src/events/plugins`, `/opt/custom_plugins`) definita in `config/event_handlers.yaml`.
- **Marketplace client**: per funzionalità legate al marketplace.
- Inizializzazione in `main.py` (lifespan): `EventConfigLoader`, `EventBus`, `PluginLoader`, `PluginManager`.

Documentazione dettagliata:

- `docs/EVENT_SYSTEM.md`
- `docs/PLUGIN_DEVELOPMENT.md`
- `docs/GUIDA_PLUGIN_SISTEMA.md`
- `docs/EVENTI_IMPLEMENTATI.md`

---

## 12. Cache

- **Backend**: Redis (opzionale), memory, hybrid (configurabile con `CACHE_BACKEND`).
- **Settings**: `src/core/settings.py` (CacheSettings, TTL, feature flag per ordini/prodotti/clienti/API esterne).
- **Middleware**: cache condizionale su alcune route (es. `setup_conditional_middleware` con TTL).
- **Legacy**: FastAPICache con Redis (se disponibile) per compatibilità.

Dettagli: `docs/CACHING_SYSTEM.md`.

---

## 13. Gestione errori

L’API usa eccezioni custom e handler globali in `src/main.py`:

| Eccezione | HTTP | Uso |
|-----------|------|-----|
| `ValidationException` | 400 | Validazione business |
| `NotFoundException` | 404 | Risorsa non trovata |
| `AlreadyExistsError` | 409 | Conflitto (es. già esistente) |
| `BusinessRuleException` | 400 | Regola di business violata |
| `AuthenticationException` | 401 | Non autenticato |
| `AuthorizationException` | 403 | Non autorizzato |
| `InfrastructureException` | 500 | Errore infrastruttura |
| `CarrierApiError` | (variabile) | Errori API corrieri |
| `RequestValidationError` (Pydantic) | 422 | Validazione input (formattata con `PydanticErrorFormatter`) |
| `StarletteHTTPException` | (variabile) | HTTP generico |
| `Exception` | 500 | Errore non gestito |

Risposta standard (es. da `BaseApplicationException` e simili):

```json
{
  "error_code": "CODICE",
  "message": "Messaggio",
  "details": {},
  "status_code": 400
}
```

Middleware: `ErrorLoggingMiddleware`, `PerformanceLoggingMiddleware`, `SecurityLoggingMiddleware` per log e monitoraggio.

---

## 14. Testing e riferimenti

- **Test**: cartella `tests/` (vedi `tests/README.md` se presente). Framework tipico: pytest, pytest-asyncio.
- **Swagger**: `http://localhost:8000/docs`.
- **OpenAPI**: schema generato da FastAPI (es. `/openapi.json`).

### Documentazione esistente in repo

- `README.md` – panoramica e avvio rapido.
- `SETUP_INIZIALE.md` – setup iniziale (se presente).
- `docs/ECOMMERCE_SYNC.md` – sincronizzazione e-commerce.
- `docs/EVENT_SYSTEM.md`, `docs/PLUGIN_DEVELOPMENT.md`, `docs/GUIDA_PLUGIN_SISTEMA.md`, `docs/EVENTI_IMPLEMENTATI.md` – eventi e plugin.
- `docs/CACHING_SYSTEM.md` – cache.
- `docs/order_state_sync_*.md` – sync stati ordine.
- `docs/carrier_*.md` – corrieri e assegnazioni.

---

## Changelog documentazione

- **v1** – Creazione documentazione completa: panoramica, stack, struttura, setup, configurazione, database, architettura, API, auth, funzionalità (ordini, resi, documenti fiscali, spedizioni, sync, eventi, cache, errori), riferimenti a doc e testing.
