# Analisi Approfondita del Progetto ECommerceManagerAPI

> Documento di riferimento per la creazione di prompt generici e specifici per modulo.
> Generato il: 16 Aprile 2026

---

## Indice

1. [Panoramica Generale](#1-panoramica-generale)
2. [Stack Tecnologico](#2-stack-tecnologico)
3. [Architettura e Pattern](#3-architettura-e-pattern)
4. [Struttura del Progetto](#4-struttura-del-progetto)
5. [Layer: Models (Database)](#5-layer-models-database)
6. [Layer: Repository](#6-layer-repository)
7. [Layer: Services](#7-layer-services)
8. [Layer: Routers (API Endpoints)](#8-layer-routers-api-endpoints)
9. [Layer: Schemas (Pydantic)](#9-layer-schemas-pydantic)
10. [Sistema di Dependency Injection](#10-sistema-di-dependency-injection)
11. [Sistema di Eventi e Plugin](#11-sistema-di-eventi-e-plugin)
12. [Sistema di Cache](#12-sistema-di-cache)
13. [Middleware](#13-middleware)
14. [Sistema di Eccezioni](#14-sistema-di-eccezioni)
15. [Integrazioni Esterne](#15-integrazioni-esterne)
16. [Subsistemi Specializzati](#16-subsistemi-specializzati)
17. [Infrastruttura e DevOps](#17-infrastruttura-e-devops)
18. [Testing](#18-testing)
19. [Catalogo Completo degli Endpoint API](#19-catalogo-completo-degli-endpoint-api)
20. [Catalogo Completo dei Models](#20-catalogo-completo-dei-models)
21. [Catalogo Completo degli Schemas](#21-catalogo-completo-degli-schemas)
22. [Convenzioni e Pattern Ricorrenti](#22-convenzioni-e-pattern-ricorrenti)
23. [Mappa delle Dipendenze tra Moduli](#23-mappa-delle-dipendenze-tra-moduli)
24. [Linee Guida per Prompt Generici](#24-linee-guida-per-prompt-generici)
25. [Template per Prompt Specifici per Modulo](#25-template-per-prompt-specifici-per-modulo)

---

## 1. Panoramica Generale

**ECommerceManagerAPI** (nome interno: "Elettronew API") e' un'applicazione backend REST API costruita con FastAPI per la gestione centralizzata di:

- **Ordini** (creazione, aggiornamento, stati, storico, resi)
- **Clienti** (anagrafica, indirizzi)
- **Prodotti** (catalogo, immagini, prezzi live)
- **Spedizioni** (integrazione multi-corriere: BRT, DHL, FedEx)
- **Documenti fiscali** (fatture, note di credito, XML FatturaPA, invio SDI)
- **DDT** (Documenti di Trasporto)
- **Preventivi** (creazione, conversione in ordini)
- **Sincronizzazione e-commerce** (PrestaShop, estendibile)
- **Import CSV** (importazione massiva entita')
- **Generazione PDF** (DDT, fatture, preventivi)
- **Sistema eventi/plugin** (architettura event-driven con plugin isolati)

L'applicazione segue i principi **SOLID** ed utilizza un'architettura a layer ben definita:
**Router -> Service -> Repository -> Model**, con **Dependency Injection** custom e **Event Bus** asincrono.

**Database:** MySQL (PyMySQL driver)
**Cache:** Redis + Memory (ibrida) con circuit breaker
**Migrazioni:** Alembic
**Autenticazione:** JWT (python-jose) con OAuth2PasswordBearer

---

## 2. Stack Tecnologico

| Componente | Tecnologia | Versione |
|---|---|---|
| Framework Web | FastAPI | 0.110.1 |
| ASGI Server | Uvicorn | 0.29.0 |
| ORM | SQLAlchemy | 2.0.29 |
| Database | MySQL | via PyMySQL 1.1.0 |
| Validazione | Pydantic | 2.6.4 |
| Settings | pydantic-settings | 2.2.1 |
| Migrazioni | Alembic | 1.13.1 |
| Cache | Redis | 6.4.0 |
| Cache Memory | cachetools | 5.3.3 |
| JWT | python-jose | 3.3.0 |
| Password Hashing | bcrypt + passlib | 4.1.2 / 1.7.4 |
| HTTP Client | httpx + aiohttp | 0.27.0 / 3.9.1 |
| Email | fastapi-mail + aiosmtplib | 1.4.1 / 2.0.2 |
| PDF | fpdf2 + pypdf | 2.7.9 / 4.0.1 |
| Serializzazione | orjson | 3.9.15 |
| Template | Jinja2 | 3.1.3 |
| Data Processing | pandas + numpy | 2.2.2 / 2.0.0 |
| Date/Time | pendulum | 3.1.0 |
| Retry | tenacity | >=8.0.0 |
| YAML | PyYAML | 6.0.1 |
| Testing | pytest + pytest-asyncio | 8.1.1 / 0.23.6 |
| Mock Redis | fakeredis | 2.20.1 |
| Containerizzazione | Docker | Python 3.11-slim |
| Monitoraggio | Prometheus + Grafana | via docker-compose |

---

## 3. Architettura e Pattern

### 3.1 Architettura a Layer

```
[Client HTTP]
     |
     v
[Middleware] ── ErrorLogging, Performance, Security, ConditionalGet (ETag), CORS
     |
     v
[Router] ── FastAPI APIRouter, validazione input (Pydantic), autenticazione JWT
     |
     v
[Service] ── Business logic, validazione regole, orchestrazione, emissione eventi
     |
     v
[Repository] ── Accesso dati, query SQL, CRUD, filtri, paginazione
     |
     v
[Model] ── SQLAlchemy ORM, definizione tabelle, relazioni
     |
     v
[Database MySQL]
```

### 3.2 Pattern Implementati

| Pattern | Implementazione |
|---|---|
| **Repository Pattern** | `BaseRepository<T, K>` + interfacce `I*Repository` |
| **Service Layer** | `I*Service` (ABC) + implementazioni concrete |
| **Dependency Injection** | `Container` custom con `register_singleton/transient`, `resolve_with_session` |
| **Factory Pattern** | `CarrierServiceFactory`, `create_ecommerce_service()` |
| **Strategy Pattern** | Corrieri (BRT/DHL/FedEx), E-commerce (PrestaShop/estendibile) |
| **Observer/Event Bus** | `EventBus` asincrono con `subscribe/publish` |
| **Plugin Architecture** | `PluginManager` + `EventHandlerPlugin` con circuit breaker |
| **Decorator Pattern** | `@emit_event_on_success`, `@cached`, `@track_cache_operation` |
| **Unit of Work** | Interfaccia `IUnitOfWork` definita (non pienamente implementata) |
| **Circuit Breaker** | Cache (errori Redis) e Plugin (5 failure / 5 min) |

### 3.3 Flusso di una Request Tipica

```
1. HTTP Request → FastAPI
2. Middleware chain (ErrorLogging → Performance → Security → ConditionalGet)
3. Router: validazione Pydantic, autenticazione JWT, risoluzione dipendenze
4. Router chiama container.resolve_with_session(IService, db_session)
5. Service: business logic, validazione regole
6. Service chiama Repository (iniettato via DI)
7. Repository: query SQLAlchemy, CRUD
8. Service: post-processing, @emit_event_on_success → EventBus
9. EventBus: dispatch asincrono a plugin/handler registrati
10. Router: costruisce response schema Pydantic
11. Middleware: aggiunge headers (X-Process-Time, ETag, Cache-Control)
12. HTTP Response → Client
```

---

## 4. Struttura del Progetto

```
ECommerceManagerAPI/
├── .gitignore
├── alembic.ini                    # Config migrazioni (gitignored)
├── conftest.py                    # Python path setup per test
├── docker-compose.yml             # Redis, API, Redis Commander, Prometheus, Grafana
├── Dockerfile                     # Python 3.11-slim, uvicorn
├── DOCUMENTAZIONE.md              # Documentazione completa (IT)
├── env.example                    # Template variabili ambiente
├── LICENSE
├── pytest.ini                     # Configurazione pytest
├── QUICK_START.md                 # Guida avvio rapido
├── README.md                      # Installazione e setup
├── redis.conf                     # Configurazione Redis
├── requirements.txt               # Dipendenze Python (73 pacchetti)
├── run_dev.ps1 / run_prod.ps1     # Script avvio PowerShell
├── setup_env.ps1                  # Setup ambiente
│
├── alembic/                       # Migrazioni database
│   ├── env.py
│   ├── script.py.mako
│   └── versions/                  # (gitignored)
│
├── config/
│   └── event_handlers.yaml        # Routing eventi → plugin
│
├── docs/                          # Documentazione tecnica
│   ├── CACHING_SYSTEM.md          # Sistema cache (643 righe)
│   ├── carrier_assignment.md
│   ├── carrier_select_options.md
│   ├── ECOMMERCE_SYNC.md          # Sincronizzazione e-commerce
│   ├── EVENTI_IMPLEMENTATI.md     # 16 eventi implementati
│   ├── EVENT_SYSTEM.md            # Sistema eventi
│   ├── EVENT_SYSTEM_STRATEGY.md   # Strategia eventi (858 righe)
│   ├── GUIDA_PLUGIN_SISTEMA.md    # Guida plugin (IT)
│   ├── PLUGIN_DEVELOPMENT.md      # Sviluppo plugin (EN)
│   ├── order_state_sync_*.md      # Sync stati ordine
│   └── sync_images_api_reference.md
│
├── monitoring/                    # Configurazione monitoring
│   ├── prometheus.yml
│   └── grafana/provisioning/datasources/prometheus.yml
│
├── scripts/                       # Script di utility
│   ├── setup_initial.py           # Setup iniziale completo
│   ├── init_app_configurations.py
│   ├── init_order_states.py
│   ├── import_data.py
│   ├── create_fixtures.py
│   ├── clear_database.py
│   ├── warm_cache.py
│   └── warm_image_cache.py
│
├── tests/                         # Suite di test
│   ├── conftest.py                # Fixtures (SQLite in-memory, auth, client)
│   ├── factories/                 # Factory per test data (16 factory)
│   ├── helpers/                   # Assert e auth helpers
│   ├── integration/api/v1/        # Test integrazione API
│   ├── unit/                      # Test unitari
│   └── e2e/                       # Test end-to-end
│
└── src/                           # Codice sorgente (~380 file)
    ├── __init__.py
    ├── database.py                # Engine, SessionLocal, Base, get_db
    ├── main.py                    # App FastAPI, middleware, routers (724 righe)
    │
    ├── core/                      # Infrastruttura trasversale
    │   ├── base_repository.py     # BaseRepository<T,K> generico
    │   ├── cache.py               # CacheManager (Redis + Memory + Circuit Breaker)
    │   ├── cached.py              # Decoratore @cached
    │   ├── container.py           # Container DI
    │   ├── container_config.py    # Registrazione dipendenze
    │   ├── dependencies.py        # Helper DI per FastAPI
    │   ├── exceptions.py          # Gerarchia eccezioni (280 righe)
    │   ├── interfaces.py          # IRepository, IBaseService, IUnitOfWork
    │   ├── invalidation.py        # Invalidazione cache
    │   ├── monitoring.py          # MetricsCollector, PerformanceMonitor
    │   ├── observability.py       # CacheMetrics, CorrelationTracker
    │   ├── pydantic_error_formatter.py
    │   ├── settings.py            # CacheSettings, CarrierIntegrationSettings, TTL_PRESETS
    │   └── static_files.py
    │
    ├── middleware/
    │   ├── conditional.py         # ETag, Cache-Control, 304 Not Modified
    │   └── error_logging.py       # ErrorLogging, Performance, Security middleware
    │
    ├── models/                    # 40 file - SQLAlchemy ORM
    │   ├── relations/relations.py # Tabelle associative (orders_history, user_roles)
    │   └── [38 modelli entita']
    │
    ├── repository/                # ~37 implementazioni + ~37 interfacce
    │   ├── interfaces/            # I*Repository (ABC)
    │   └── [implementazioni concrete]
    │
    ├── routers/                   # 37 file - Endpoint API
    │   ├── dependencies.py        # Dipendenze condivise (paginazione, DB)
    │   └── [36 router modules]
    │
    ├── schemas/                   # 44 file - Pydantic models
    │   └── [schema per ogni entita' + request/response types]
    │
    ├── services/
    │   ├── core/                  # Utility (query_utils, tool, wrap)
    │   ├── routers/               # 41 file - Service per ogni router
    │   ├── interfaces/            # 38 file - I*Service (ABC)
    │   ├── ecommerce/             # Sync e-commerce
    │   │   ├── base_ecommerce_service.py
    │   │   ├── prestashop_service.py
    │   │   ├── service_factory.py
    │   │   └── shipments/         # Client corrieri (BRT, DHL, FedEx)
    │   ├── csv_import/            # Import CSV pipeline
    │   ├── pdf/                   # Generazione PDF (DDT, fatture, preventivi)
    │   ├── sync/                  # Sync periodici (tracking, order states, FatturaPA)
    │   └── external/              # Servizi esterni (FatturaPA, province)
    │
    ├── factories/services/
    │   └── carrier_service_factory.py  # Factory corrieri
    │
    └── events/                    # Sistema eventi
        ├── core/                  # EventBus, Event, EventType
        ├── config/                # Loader YAML, schema config
        ├── decorators.py          # @emit_event_on_success
        ├── runtime.py             # Singleton EventBus, emit_event()
        ├── plugin_manager.py      # Gestione plugin con circuit breaker
        ├── plugin_loader.py       # Discovery e caricamento plugin
        ├── marketplace/           # Client e installer marketplace
        └── plugins/               # Plugin installati
            ├── customs/as400_validate_order_megawatt/
            ├── email_notification/
            └── platform_state_sync/
```

---

## 5. Layer: Models (Database)

### 5.1 Base e Configurazione

- **Base:** `sqlalchemy.orm.declarative_base()` in `src/database.py`
- **Engine:** MySQL via PyMySQL, connection string da variabili ambiente
- **Session:** `SessionLocal = sessionmaker(autocommit=False, autoflush=False)`
- **Migrazioni:** Alembic con `alembic/env.py` che importa tutti i modelli

### 5.2 Tabelle Associative (M2M)

Definite in `src/models/relations/relations.py`:

| Tabella | Colonne | Scopo |
|---|---|---|
| `orders_history` | `id_order` (FK), `id_order_state` (FK), `date_add` | Storico stati ordine (M2M Order ↔ OrderState) |
| `user_roles` | `id_user` (FK), `id_role` (FK) | Ruoli utente (M2M User ↔ Role) |

### 5.3 Entita' Principali e Relazioni

#### Order (`orders`)
- **PK:** `id_order`
- **FK:** `id_platform` → platforms, `id_store` → stores, `id_carrier` → carriers, `id_shipping` → shipments, `id_ecommerce_state` → ecommerce_order_states
- **Relazioni:** `platform`, `store`, `order_states` (M2M via orders_history), `carrier`, `shipments`, `orders_document`, `fiscal_documents`, `order_packages`, `ecommerce_order_state`
- **Colonne notevoli:** `reference`, `internal_reference`, `id_origin`, totali (with_tax, net, product), flags (`is_invoice_requested`, `is_payed`, `is_multishipping`), `date_add`, `updated_at`

#### Customer (`customers`)
- **PK:** `id_customer`
- **FK:** `id_store` → stores
- **Relazioni:** `store`, `addresses`, `orders_document`

#### Product (`products`)
- **PK:** `id_product`
- **FK:** `id_category` → categories, `id_brand` → brands, `id_store` → stores
- **Relazioni:** `store`, `brand`, `category`

#### OrderDetail (`order_details`)
- **PK:** `id_order_detail`
- **Colonne:** `id_order`, `id_order_document`, `id_product`, `id_tax` (integer, NESSUN FK ORM)
- **Nota:** relazioni gestite solo a livello logico, non via `ForeignKey()`/`relationship()`

#### Shipping (`shipments`)
- **PK:** `id_shipping`
- **Colonne:** `id_carrier_api`, `id_shipping_state`, `id_tax` (integer, no FK ORM)
- **Relazioni:** `orders` (back_populates dall'FK su Order)

#### FiscalDocument (`fiscal_documents`)
- **PK:** `id_fiscal_document`
- **FK:** `id_order` → orders, `id_store` → stores, `id_fiscal_document_ref` → fiscal_documents (self-ref)
- **Relazioni:** `store`, `order`, `referenced_document`/`credit_notes` (self), `details` → FiscalDocumentDetail

#### OrderDocument (`orders_document`)
- **PK:** `id_order_document`
- **FK:** `id_order` → orders, `id_store` → stores, `id_customer` → customers, `id_address_delivery/invoice` → addresses, `id_sectional` → sectionals, `id_shipping` → shipments, `id_payment` → payments

#### Store (`stores`)
- **PK:** `id_store`
- **FK:** `id_platform` → platforms
- **Relazioni estese:** `platform`, `orders`, `products`, `customers`, `addresses`, `fiscal_documents`, `order_documents`, `app_configurations`, `company_fiscal_infos`, `carrier_assignments`, `carriers`, `payments`, `state_triggers`, `ecommerce_order_states`
- **Helper methods:** `get_default_vat_number`, `get_default_country_code`, `get_default_fiscal_info`, `get_logo_path`

#### User (`users`)
- **PK:** `id_user`
- **M2M:** `roles` via `user_roles`

### 5.4 Elenco Completo Tabelle

| Tabella | Model | File |
|---|---|---|
| `addresses` | Address | address.py |
| `app_configurations` | AppConfiguration | app_configuration.py |
| `brands` | Brand | brand.py |
| `brt_configurations` | BrtConfiguration | brt_configuration.py |
| `carrier_assignments` | CarrierAssignment | carrier_assignment.py |
| `carrier_prices` | CarrierPrice | carrier_price.py |
| `carriers` | Carrier | carrier.py |
| `carriers_api` | CarrierApi | carrier_api.py |
| `categories` | Category | category.py |
| `company_fiscal_info` | CompanyFiscalInfo | company_fiscal_info.py |
| `countries` | Country | country.py |
| `customers` | Customer | customer.py |
| `dhl_configurations` | DhlConfiguration | dhl_configuration.py |
| `ecommerce_order_states` | EcommerceOrderState | ecommerce_order_state.py |
| `fedex_configurations` | FedexConfiguration | fedex_configuration.py |
| `fiscal_document_details` | FiscalDocumentDetail | fiscal_document_detail.py |
| `fiscal_documents` | FiscalDocument | fiscal_document.py |
| `fatture_acquisto_sync` | PurchaseInvoiceSync | purchase_invoice_sync.py |
| `languages` | Lang | lang.py |
| `messages` | Message | message.py |
| `order_details` | OrderDetail | order_detail.py |
| `order_packages` | OrderPackage | order_package.py |
| `order_states` | OrderState | order_state.py |
| `orders` | Order | order.py |
| `orders_document` | OrderDocument | order_document.py |
| `orders_history` | (association table) | relations.py |
| `payments` | Payment | payment.py |
| `platform_state_triggers` | PlatformStateTrigger | platform_state_trigger.py |
| `platforms` | Platform | platform.py |
| `products` | Product | product.py |
| `roles` | Role | role.py |
| `sectionals` | Sectional | sectional.py |
| `shipment_documents` | ShipmentDocument | shipment_document.py |
| `shipments` | Shipping | shipping.py |
| `shipments_history` | ShipmentsHistory | shipments_history.py |
| `shipping_state` | ShippingState | shipping_state.py |
| `stores` | Store | store.py |
| `taxes` | Tax | tax.py |
| `user_roles` | (association table) | relations.py |
| `users` | User | user.py |

---

## 6. Layer: Repository

### 6.1 Base Repository

`src/core/base_repository.py` - `BaseRepository(Generic[T, K], IRepository[T, K])`

**Funzionalita':**
- CRUD generico: `get_by_id`, `get_by_id_or_raise`, `get_all` (con filtri), `create`, `update`, `delete`, `bulk_create`
- Filtraggio automatico: lista → `IN`, stringa con `%` → `LIKE`, altrimenti `=`
- Paginazione: `paginate(query, offset, limit)`, `get_offset(page, limit)`, `get_count(query)`
- Discovery automatica PK: `_get_id_field()` cerca `id`, `id_<model_name>`
- Error handling: rollback su eccezioni mutanti, wrapping in `InfrastructureException`/`NotFoundException`
- Accetta input come dict, ORM instance, o Pydantic model (via `model_dump`)

### 6.2 Pattern Repository Concreto

Ogni repository:
1. Estende `BaseRepository[Model, KeyType]`
2. Implementa un'interfaccia `I*Repository` (da `src/repository/interfaces/`)
3. Riceve `Session` nel costruttore
4. Puo' aggiungere metodi specifici (query complesse, join, filtri business)

**Esempio tipico:**
```python
class OrderRepository(BaseRepository[Order, int], IOrderRepository):
    def __init__(self, session: Session):
        super().__init__(session, Order)
    
    def get_all(self, offset, limit, filters...) -> tuple:
        # Query complessa con join, filtri, conteggio
        ...
```

### 6.3 Repository Speciali

- **`CachedOrderRepository`**: wrapper con cache per `OrderRepository`
- **`CachedLookupRepositories`**: cache per tabelle di lookup (categorie, brand, etc.)

---

## 7. Layer: Services

### 7.1 Interfacce Service

Definite in `src/services/interfaces/`, ogni interfaccia e' una classe ABC che estende `IBaseService`:

```python
class IBaseService(ABC):
    @abstractmethod
    async def validate_business_rules(self, data: Any) -> None:
        pass
```

### 7.2 Service Concreti

In `src/services/routers/`, ogni service:
1. Implementa la relativa interfaccia
2. Riceve repository (e opzionalmente altri service) tramite DI
3. Contiene la business logic
4. Usa `@emit_event_on_success` per emettere eventi
5. Usa le eccezioni tipizzate (`NotFoundException`, `BusinessRuleException`, etc.)

### 7.3 Services Specializzati

| Directory | Scopo |
|---|---|
| `services/core/` | Utility condivise (`query_utils`, `tool`, `wrap`) |
| `services/ecommerce/` | Sync e-commerce (PrestaShop base + factory) |
| `services/ecommerce/shipments/` | Client corrieri (BRT, DHL, FedEx) + mapper + status |
| `services/csv_import/` | Pipeline import CSV (parse → validate → map → bulk insert) |
| `services/pdf/` | Generazione PDF (DDT, fatture, preventivi) con fpdf2 |
| `services/sync/` | Task periodici (tracking polling, order state sync, FatturaPA pool) |
| `services/external/` | Integrazioni esterne (FatturaPA, province italiane) |

### 7.4 query_utils.py - Utility Condivise

Funzioni helper usate trasversalmente:
- `parse_int_list(value)`: converte stringa comma-separated o iterable in lista int
- `filter_by_id(query, column, value)`: filtro per ID singolo o lista
- `filter_by_string(query, column, value)`: filtro LIKE per stringhe
- `search_in_every_field(query, search, fields)`: ricerca full-text su piu' campi (OR + ILIKE)
- `filter_by_date(query, column, date_from, date_to)`: filtro per range date
- `edit_entity(entity, schema)`: applica `model_dump(exclude_unset=True)` su entita' ORM
- `create_and_set_id(entity, session)`: flush + refresh per ottenere ID auto-generato

---

## 8. Layer: Routers (API Endpoints)

### 8.1 Struttura Router

Tutti i router usano il prefisso base `/api/v1/` e sono registrati in `src/main.py`.

**Pattern tipico:**
```python
router = APIRouter(prefix="/api/v1/entity", tags=["Entity"])

@router.get("/")
def get_all(db: Session = Depends(get_db), offset: int = 0, limit: int = 100):
    service = container.resolve_with_session(IEntityService, db)
    return service.get_all(offset, limit)
```

### 8.2 Dipendenze Condivise

`src/routers/dependencies.py` definisce:
- `db_dependency`: `Annotated[Session, Depends(get_db)]`
- Parametri di paginazione (offset, limit con MAX_LIMIT da env)

### 8.3 Autenticazione

- **JWT** via `python-jose` con `OAuth2PasswordBearer`
- Endpoint login: `POST /api/v1/auth/login` → restituisce `Token` (access_token)
- Endpoint registrazione: `POST /api/v1/auth/register`
- I router protetti usano `Depends(get_current_user)` o ruoli specifici

---

## 9. Layer: Schemas (Pydantic)

### 9.1 Convenzioni Naming

| Suffisso | Scopo |
|---|---|
| `*Schema` | Input/base model |
| `*ResponseSchema` | Singola entita' in risposta |
| `*UpdateSchema` | Aggiornamento parziale |
| `*CreateSchema` | Creazione con campi specifici |
| `All*ResponseSchema` | Lista paginata con conteggio |
| `*IdSchema` | Solo ID (per reference) |

### 9.2 Configurazione Pydantic

Tutti gli schema usano Pydantic v2 con:
```python
class Config:
    from_attributes = True  # Per ORM mode
```

---

## 10. Sistema di Dependency Injection

### 10.1 Container (`src/core/container.py`)

Container DI custom con tre modalita' di registrazione:

| Tipo | Metodo | Lifecycle |
|---|---|---|
| **Singleton** | `register_singleton(interface, factory)` | Una istanza per tutta l'app |
| **Transient** | `register_transient(interface, implementation)` | Nuova istanza per ogni resolve |
| **Instance** | `register_instance(interface, instance)` | Oggetto pre-creato |

### 10.2 Risoluzione

- **`resolve(interface)`**: costruisce istanza via `inspect.signature`, risolve ricorsivamente le dipendenze
- **`resolve_with_session(interface, session)`**: risolve iniettando la `Session` DB corrente (transient: costruttore, singleton: `_session` attribute)

### 10.3 Configurazione (`src/core/container_config.py`)

`configure_container()` registra tutte le coppie interfaccia → implementazione:
- **Repository**: `ICustomerRepository` → `CustomerRepository` (transient)
- **Services**: `IOrderService` → `OrderService` (transient)
- **Client API**: `DhlClient`, `BrtClient`, `FedexClient` (singleton)
- **Mapper**: `DhlMapper`, `BrtMapper`, `FedexMapper` (transient)

### 10.4 Uso nei Router

```python
# Pattern tipico nei router
from src.core.container_config import get_configured_container
container = get_configured_container()

@router.get("/")
def get_all(db: Session = Depends(get_db)):
    service = container.resolve_with_session(IEntityService, db)
    return service.get_all()
```

---

## 11. Sistema di Eventi e Plugin

### 11.1 Architettura

```
Service (@emit_event_on_success)
    → emit_event(Event)
        → EventBus.publish(event)
            → PluginManager._handle_event(event)
                → Per ogni plugin abilitato:
                    → handler.handle(event)
```

### 11.2 EventType (`src/events/core/event.py`)

Enum con i tipi di evento disponibili:

| Categoria | Eventi |
|---|---|
| **Ordini** | `ORDER_CREATED`, `ORDER_UPDATED`, `ORDER_DELETED`, `ORDER_STATUS_CHANGED`, `ORDER_BULK_STATUS_CHANGED` |
| **Spedizioni** | `SHIPMENT_CREATED`, `SHIPMENT_MULTI_CREATED`, `SHIPMENT_CANCELLED` |
| **Documenti** | `DOCUMENT_CREATED`, `DOCUMENT_UPDATED`, `DOCUMENT_DELETED`, `DOCUMENT_CONVERTED` |
| **Clienti** | `CUSTOMER_CREATED`, `CUSTOMER_UPDATED`, `CUSTOMER_DELETED` |
| **Prodotti** | `PRODUCT_CREATED`, `PRODUCT_UPDATED`, `PRODUCT_DELETED` |
| **Indirizzi** | `ADDRESS_CREATED`, `ADDRESS_UPDATED`, `ADDRESS_DELETED` |
| **Sync** | `PRESTASHOP_SYNC_COMPLETED` |
| **Import** | `CSV_IMPORT_COMPLETED` |
| **Plugin** | `PLUGIN_LOADED`, `PLUGIN_UNLOADED` |

### 11.3 Event (dataclass)

```python
@dataclass(frozen=True, slots=True)
class Event:
    event_type: str
    data: Dict
    metadata: Dict  # include idempotency_key auto-generata
    timestamp: datetime  # UTC
```

### 11.4 EventBus (`src/events/core/event_bus.py`)

- Asincrono (`asyncio`)
- `subscribe(event_type, handler)` / `unsubscribe`
- `publish(event)`: dispatch parallelo con `asyncio.gather`, semaphore per concorrenza
- Error handling: `HandlerExecutionError` con lista `HandlerFailure`

### 11.5 Plugin Manager (`src/events/plugin_manager.py`)

- Discovery plugin da directory configurate
- Circuit breaker: 5 failure consecutive → plugin disabilitato per 5 minuti
- Lifecycle: `on_load` / `on_unload` per ogni plugin
- Config routing via YAML (`config/event_handlers.yaml`)

### 11.6 Plugin Installati

| Plugin | Scopo |
|---|---|
| `as400_validate_order_megawatt` | Validazione ordini via SOAP AS400 (custom per Megawatt) |
| `email_notification` | Notifiche email su eventi |
| `platform_state_sync` | Sincronizzazione stati con piattaforma e-commerce |

### 11.7 Decoratore `@emit_event_on_success`

```python
@emit_event_on_success(
    event_type=EventType.ORDER_CREATED,
    data_extractor=lambda result: {"order_id": result.id_order},
    metadata_extractor=lambda: {"source": "api"}
)
def create_order(self, data):
    # business logic
    return new_order
```

---

## 12. Sistema di Cache

### 12.1 Architettura

- **Ibrida**: Memory (cachetools `TTLCache`) + Redis (`aioredis`)
- **Backend configurabile**: `redis`, `memory`, `hybrid` (env: `CACHE_BACKEND`)
- **Circuit Breaker**: su errori Redis, fallback automatico su memory

### 12.2 CacheManager (`src/core/cache.py`)

- `initialize()`: connessione Redis con fallback su memory
- `get(namespace, **params)` / `set(namespace, value, ttl, **params)`
- `_build_key()`: chiave con salt + MD5 se > 100 chars
- Metriche: hit/miss/latency/error via `CacheMetrics`

### 12.3 Decoratore `@cached` (`src/core/cached.py`)

```python
@cached(
    ttl=300,              # Oppure preset="orders_list"
    key="orders:{page}",  # Template o callable
    layer="auto",          # auto/memory/redis
    stale_ttl=900,         # Stale-while-revalidate
    single_flight=True,    # Deduplica richieste concorrenti
    tenant_from_user=True  # Multi-tenancy
)
async def get_orders(page: int): ...
```

### 12.4 TTL Presets (`src/core/settings.py`)

| Categoria | Preset | TTL |
|---|---|---|
| Lookup statici | `order_states`, `categories`, `brands`, `carriers`, `countries`, `langs` | 24h |
| Config | `config` | 15min |
| Dettaglio entita' | `customer` 1h, `product` 6h, `order` 2min, `address` 2h |
| Liste | `customers_list` 30s, `products_list` 1min, `orders_list` 30s |
| API esterne | `prestashop_orders` 2min, `fatturapa_pool` 1min |
| Init data | `init_static` 7gg, `init_dynamic` 1gg, `init_full` 30min |
| Eventi | `events_list` 30gg |

### 12.5 Invalidazione

- Manuale: `invalidate_pattern`, `invalidate_entity`
- Context manager: `CacheContext` per invalidazione atomica
- Post-commit: `invalidate_on_commit`
- SQLAlchemy hooks (quando configurati)

---

## 13. Middleware

### 13.1 Stack Middleware (ordine in `main.py`)

1. **`CORSMiddleware`** (Starlette) - Origini consentite, metodi, headers
2. **`ErrorLoggingMiddleware`** - Log richieste/risposte/errori con request_id
3. **`PerformanceLoggingMiddleware`** - Richieste lente (threshold 1.0s)
4. **`SecurityLoggingMiddleware`** - Accesso endpoint sensibili, errori 4xx+
5. **`ConditionalGetMiddleware`** - ETag, If-None-Match, 304, Cache-Control

### 13.2 ConditionalGetMiddleware (`src/middleware/conditional.py`)

- Genera ETag da hash MD5 del body JSON
- Confronta `If-None-Match` → 304 Not Modified
- Aggiunge `Cache-Control`, `Vary` headers
- Lista configurabile di endpoint cacheable
- Circa 480 righe

### 13.3 ErrorLoggingMiddleware (`src/middleware/error_logging.py`)

- `X-Process-Time` e `X-Request-ID` headers su ogni risposta
- Log strutturato con metadata (method, path, query_params, client_ip, user_agent)
- Traceback completo su errori

---

## 14. Sistema di Eccezioni

### 14.1 Gerarchia (`src/core/exceptions.py`)

```
BaseApplicationException (ABC, Exception)
├── DomainException (400)
│   ├── ValidationException
│   └── BusinessRuleException
├── NotFoundException (404)
├── InfrastructureException (500)
│   ├── EcommerceApiResponseError
│   └── (generic database/network errors)
├── CarrierApiError (variabile)
├── AuthenticationException (401)
├── AuthorizationException (403)
└── AlreadyExistsError (409)
```

### 14.2 ErrorCode (Enum)

Codici standardizzati: `VALIDATION_ERROR`, `EMAIL_DUPLICATE`, `BUSINESS_RULE_VIOLATION`, `ORDER_NOT_MODIFIABLE`, `ENTITY_NOT_FOUND`, `DATABASE_ERROR`, `EXTERNAL_SERVICE_ERROR`, `CARRIER_API_ERROR`, `UNAUTHORIZED`, `FORBIDDEN`, `TOKEN_EXPIRED`, etc.

### 14.3 ExceptionFactory

Factory per eccezioni comuni: `customer_not_found(id)`, `order_not_found(id)`, `email_duplicate(email)`, `required_field_missing(field)`, `order_not_modifiable(id, reason)`.

### 14.4 Mapping in main.py

Exception handler globali in `main.py` che mappano le eccezioni tipizzate a risposte HTTP JSON con codici appropriati.

---

## 15. Integrazioni Esterne

### 15.1 PrestaShop (`src/services/ecommerce/`)

- **`BaseEcommerceService`** (ABC): context manager asincrono, carica config store
- **`PrestaShopService`**: sync completo/incrementale di ordini, clienti, prodotti, categorie, brand, indirizzi, immagini
- **`service_factory.py`**: `create_ecommerce_service(store_id, db)` → istanzia in base a `platform.name`
- Attualmente supportato: **solo PrestaShop**; architettura pronta per Shopify e altri

### 15.2 Corrieri (`src/services/ecommerce/shipments/`)

| Corriere | Client | Autenticazione | Caratteristiche |
|---|---|---|---|
| **BRT** | `BrtClient` (httpx) | API Key | Error mapping custom, warning non-bloccanti |
| **DHL** | `DhlClient` (httpx) | Basic Auth + idempotency ref | MyDHL Express API, sandbox/prod |
| **FedEx** | `FedexClient` (httpx) | OAuth 2.0 (token cache) | Sandbox/prod, token refresh |

Per ogni corriere: `*_client.py` (HTTP), `*_mapper.py` (mapping request/response), `*_status_mapping.py` (mapping stati)

**Factory:** `CarrierServiceFactory` seleziona il service corretto (`IShipmentService`, `ITrackingService`) in base al tipo corriere (`CarrierTypeEnum`).

### 15.3 FatturaPA (`src/services/external/fatturapa_service.py`)

- Generazione XML FatturaPA (formato FPR12)
- Upload su portale FatturaPA (Azure blob)
- Pool SDI per ricezione fatture acquisto
- Validazione tramite `FatturaPAValidator` (regole estese)

### 15.4 Province Italiane (`src/services/external/province_service.py`)

- Mapping nome provincia → sigla (2 lettere)
- Dati da `data/comuni.json` con fallback su dizionario manuale

---

## 16. Subsistemi Specializzati

### 16.1 Import CSV (`src/services/csv_import/`)

**Pipeline:**
1. `CSVParser.parse_csv()` → parsing con encoding/delimiter auto-detect
2. `DependencyResolver.validate_dependencies()` → verifica dipendenze tra entita'
3. `EntityMapper.map_to_schema()` → mapping righe CSV → schema Pydantic
4. `CSVValidator.validate_batch()` → validazione Pydantic + duplicati + FK + business rules
5. Bulk insert via repository

**Entita' supportate:** products, customers, addresses, brands, categories, carriers, countries, languages, payments, orders, order_details

**Grafo dipendenze:**
- `order_details` → orders, products
- `orders` → customers, addresses, carriers, stores, payments
- `addresses` → customers, countries
- `products` → categories, brands

### 16.2 Generazione PDF (`src/services/pdf/`)

| Tipo | Service | Contenuto |
|---|---|---|
| **DDT** | `DDTPDFService` | Documento di trasporto: mittente, destinatario, articoli, IVA, trasporto |
| **Fattura/NC** | `FiscalDocumentPDFService` | Fattura o nota di credito: dati fiscali, righe, sconti, IVA |
| **Preventivo** | `PreventivoPDFService` | Preventivo: articoli, spedizione, IVA, totali, condizioni |

Tutti usano **fpdf2** con layout personalizzato, header/footer, logo store.

### 16.3 Preventivi (`src/routers/preventivi.py`)

Sistema completo per gestione preventivi:
- CRUD preventivi con articoli
- Duplicazione
- Conversione in ordini (singola e bulk)
- Operazioni bulk (delete, update articoli, remove articoli)
- Generazione PDF
- Statistiche

### 16.4 DDT (`src/routers/ddt.py`)

Documenti di Trasporto:
- Generazione da ordine
- Creazione parziale (subset di righe ordine)
- Merge articoli
- CRUD righe
- Generazione PDF

### 16.5 Sync Periodici (`src/services/sync/`)

| Task | Funzione | Intervallo |
|---|---|---|
| **Tracking Polling** | Interroga API corrieri per aggiornamenti tracking | Dinamico (BRT: 450s-5400s, DHL/FedEx: 3600s) |
| **Order State Sync** | Sincronizza stati ordine da piattaforma e-commerce | 3600s (1 ora) |
| **FatturaPA Pool** | Scarica fatture acquisto da SDI | Su richiesta (via API) |

### 16.6 Init Data (`src/routers/init.py`)

Endpoint per bootstrap frontend:
- `GET /api/v1/init/` → payload completo (`InitDataSchema`)
- `GET /api/v1/init/static` → dati statici (platforms, languages, countries, taxes)
- `GET /api/v1/init/dynamic` → dati dinamici (sectionals, order_states, shipping_states)
- Pesantemente cachato (`init_static` 7gg, `init_dynamic` 1gg)

---

## 17. Infrastruttura e DevOps

### 17.1 Docker

**Dockerfile:**
- Base: `python:3.11-slim`
- Dipendenze: curl, gcc, g++, libpq-dev
- Non-root user: `appuser`
- Healthcheck: `curl http://localhost:8000/health`
- Entrypoint: `uvicorn src.main:app --reload`

**docker-compose.yml** - 5 servizi:

| Servizio | Immagine | Porta | Scopo |
|---|---|---|---|
| `redis` | redis:7-alpine | 6379 | Cache + pub/sub |
| `api` | build locale | 8000 | Applicazione FastAPI |
| `redis-commander` | rediscommander | 8081 | UI gestione Redis |
| `prometheus` | prom/prometheus | 9090 | Metriche |
| `grafana` | grafana/grafana | 3000 | Dashboard |

### 17.2 Variabili Ambiente (da `env.example`)

| Gruppo | Variabili Chiave |
|---|---|
| **Database** | `DATABASE_MAIN_ADDRESS/PORT/NAME/USER/PASSWORD` |
| **Security** | `SECRET_KEY` (JWT) |
| **Cache** | `CACHE_ENABLED/BACKEND`, `REDIS_URL`, TTL settings |
| **App** | `MAX_LIMIT`, `LIMIT_DEFAULT`, `ENVIRONMENT`, `DEBUG` |
| **PrestaShop** | `PRESTASHOP_API_KEY`, `PRESTASHOP_BASE_URL` |
| **FatturaPA** | `FATTURAPA_API_KEY`, `FATTURAPA_BASE_URL` |
| **Azienda** | `COMPANY_VAT_NUMBER/NAME/ADDRESS/...` |
| **Email** | `SMTP_HOST/PORT/USERNAME/PASSWORD` |
| **Tracking** | `TRACKING_POLLING_ENABLED` |

### 17.3 Script di Setup

| Script | Scopo |
|---|---|
| `setup_initial.py` | Setup completo: Order/Shipping State, AppConfig, Platform, Store, Role, Admin, CompanyFiscalInfo |
| `init_app_configurations.py` | Solo configurazioni app |
| `init_order_states.py` | Solo stati ordine |
| `import_data.py` | Importazione dati da DB sorgente |
| `clear_database.py` | Pulizia database |
| `warm_cache.py` | Pre-caricamento cache |
| `warm_image_cache.py` | Pre-caricamento cache immagini |

---

## 18. Testing

### 18.1 Configurazione

- **Framework:** pytest 8.1.1 + pytest-asyncio 0.23.6
- **DB test:** SQLite in-memory (override engine in `tests/conftest.py`)
- **Cache test:** fakeredis (mock Redis)
- **Marker:** `slow`, `integration`, `unit`, `e2e`, `order`, `webtest`
- **Timeout:** 300s

### 18.2 Fixtures Principali (`tests/conftest.py`)

- `db_session`: sessione SQLite in-memory con rollback
- `test_app`: FastAPI TestClient con override DB e cache
- `admin_client`: client con ruolo admin
- `FakeShipmentService` / `FakeCarrierServiceFactory`: mock corrieri
- `EventBusSpy`: spy per verificare eventi emessi
- Ruoli pre-configurati: admin, ordini, user

### 18.3 Factories (`tests/factories/`)

16 factory per generare dati di test:
`address`, `brands`, `carriers`, `categories`, `countries`, `country`, `customer`, `lang`, `order`, `platforms`, `products`, `roles`, `sectionals`, `shipping`, `stores`, `taxes`

### 18.4 Test Integration (`tests/integration/api/v1/`)

- `test_auth.py` - Autenticazione JWT
- `test_cache.py` - Sistema cache
- `test_categories.py` - CRUD categorie
- `test_orders.py` - CRUD ordini (piu' complesso)
- `test_shippings_create.py` - Creazione spedizioni
- `test_shippings_multi.py` - Multi-spedizioni
- `test_sync_prestashop.py` - Sync PrestaShop

---

## 19. Catalogo Completo degli Endpoint API

### Address - `/api/v1/addresses`
| Metodo | Path | Funzione |
|---|---|---|
| GET | `/` | `get_all_addresses` |
| GET | `/customer/{customer_id}` | `get_addresses_by_customer` |
| GET | `/{address_id}` | `get_address_by_id` |
| POST | `/` | `create_address` |
| PUT | `/{address_id}` | `update_address` |
| DELETE | `/{address_id}` | `delete_address` |

### ApiCarrier - `/api/v1/api_carriers`
| Metodo | Path | Funzione |
|---|---|---|
| GET | `/` | `get_all_carriers_api` |
| GET | `/{carrier_api_id}` | `get_carrier_api_by_id` |
| POST | `/` | `create_carrier_api` |
| PUT | `/{carrier_api_id}` | `update_carrier_api` |
| DELETE | `/{carrier_api_id}` | `delete_carrier_api` |

### AppConfiguration - `/api/v1/app_configurations`
| Metodo | Path | Funzione |
|---|---|---|
| GET | `/` | `get_all_app_configurations` |
| GET | `/by-category/{category}` | `get_app_configurations_by_category` |
| GET | `/{app_configuration_id}` | `get_app_configuration_by_id` |
| POST | `/` | `create_app_configuration` |
| PUT | `/{app_configuration_id}` | `update_app_configuration` |
| DELETE | `/{app_configuration_id}` | `delete_app_configuration` |

### Authentication - `/api/v1/auth`
| Metodo | Path | Funzione |
|---|---|---|
| POST | `/register` | `create_user` |
| POST | `/login` | `get_token` |

### Brand - `/api/v1/brands`
| Metodo | Path | Funzione |
|---|---|---|
| GET | `/` | `get_all_brands` |
| GET | `/{brand_id}` | `get_brand_by_id` |
| POST | `/` | `create_brand` |
| PUT | `/{brand_id}` | `update_brand` |
| DELETE | `/{brand_id}` | `delete_brand` |

### Carrier - `/api/v1/carriers`
| Metodo | Path | Funzione |
|---|---|---|
| GET | `/` | `get_all_carriers` |
| GET | `/price` | `get_carrier_price` |
| GET | `/{carrier_id}` | `get_carrier_by_id` |
| POST | `/` | `create_carrier` |
| PUT | `/{carrier_id}` | `update_carrier` |
| DELETE | `/{carrier_id}` | `delete_carrier` |

### CarrierAssignment - `/api/v1/carrier-assignments`
| Metodo | Path | Funzione |
|---|---|---|
| GET | `/` | `get_all_carrier_assignments` |
| GET | `/{assignment_id}` | `get_carrier_assignment_by_id` |
| POST | `/` | `create_carrier_assignment` |
| PUT | `/{assignment_id}` | `update_carrier_assignment` |
| DELETE | `/{assignment_id}` | `delete_carrier_assignment` |

### CarriersConfiguration - `/api/v1/carriers_configuration`
Per BRT, FedEx, DHL:
| Metodo | Path | Funzione |
|---|---|---|
| POST | `/{brt\|fedex\|dhl}/{carrier_api_id}` | create |
| GET | `/{brt\|fedex\|dhl}/{carrier_api_id}` | read |
| PUT | `/{brt\|fedex\|dhl}/{carrier_api_id}` | update |
| DELETE | `/{brt\|fedex\|dhl}/{carrier_api_id}` | delete |

### Category - `/api/v1/categories`
CRUD standard: GET `/`, GET `/{id}`, POST `/`, PUT `/{id}`, DELETE `/{id}`

### Country - `/api/v1/countries`
CRUD standard: GET `/`, GET `/{id}`, POST `/`, PUT `/{id}`, DELETE `/{id}`

### CSV Import - `/api/v1/sync/import`
| Metodo | Path | Funzione |
|---|---|---|
| POST | `/csv` | `import_csv` |
| GET | `/templates/{entity_type}` | `get_csv_template` |
| GET | `/supported-entities` | `get_supported_entities` |

### Customer - `/api/v1/customers`
| Metodo | Path | Funzione |
|---|---|---|
| GET | `/` | `get_all_customers` |
| GET | `/{customer_id}` | `get_customer_by_id` |
| POST | `/` | `create_customer` |
| PUT | `/{customer_id}` | `update_customer` |
| DELETE | `/{customer_id}` | `delete_customer` |

### DDT - `/api/v1/ddt`
| Metodo | Path | Funzione |
|---|---|---|
| GET | `/` | `get_ddt_list` |
| POST | `/` | `create_ddt` |
| POST | `/create-partial` | `create_ddt_partial` |
| POST | `/merge-articolo` | `merge_articolo_to_ddt` |
| POST | `/generate-from-order/{id_order}` | `generate_ddt_from_order` |
| GET | `/pdf/{id_order_document}` | `generate_ddt_pdf` |
| GET | `/{id_order_document}` | `get_ddt_detail` |
| PUT | `/articoli/{id_order_detail}` | `update_ddt_articolo` |
| DELETE | `/articoli/{id_order_detail}` | `delete_ddt_articolo` |

### Events - `/api/v1/events`
| Metodo | Path | Funzione |
|---|---|---|
| POST | `/reload-config` | `reload_event_configuration` |
| GET | `/plugins` | `list_event_plugins` |
| POST | `/plugins/{plugin_name}/enable` | `enable_event_plugin` |
| POST | `/plugins/{plugin_name}/disable` | `disable_event_plugin` |
| DELETE | `/plugins/{plugin_name}/uninstall` | `uninstall_event_plugin` |
| GET | `/list` | `get_events_list` |

### FiscalDocuments - `/api/v1/fiscal_documents`
| Metodo | Path | Funzione |
|---|---|---|
| POST | `/invoices` | `create_invoice` |
| GET | `/invoices/order/{id_order}` | `get_invoices_by_order` |
| POST | `/credit-notes` | `create_credit_note` |
| GET | `/credit-notes/invoice/{id_invoice}` | `get_credit_notes_by_invoice` |
| GET | `/{id_fiscal_document}` | `get_fiscal_document` |
| GET | `/` | `get_fiscal_documents` |
| DELETE | `/{id_fiscal_document}` | `delete_fiscal_document` |
| POST | `/{id_fiscal_document}/generate-xml` | `generate_xml` |
| PATCH | `/{id_fiscal_document}/status` | `update_status` |
| POST | `/{id_fiscal_document}/send-to-sdi` | `send_to_sdi` |
| GET | `/{id_fiscal_document}/pdf` | `generate_fiscal_document_pdf` |

### Init - `/api/v1/init`
| Metodo | Path | Funzione |
|---|---|---|
| GET | `/` | `get_init_data` |
| GET | `/static` | `get_static_data_only` |
| GET | `/dynamic` | `get_dynamic_data_only` |
| GET | `/health` | `get_init_health` |

### Lang - `/api/v1/languages`
CRUD standard: GET `/`, GET `/{id}`, POST `/`, PUT `/{id}`, DELETE `/{id}`

### Message - `/api/v1/messages`
CRUD standard: GET `/`, GET `/{id}`, POST `/`, PUT `/{id}`, DELETE `/{id}`

### Order - `/api/v1/orders`
| Metodo | Path | Funzione |
|---|---|---|
| GET | `/` | `get_all_orders` |
| GET | `/{order_id}` | `get_order_by_id` |
| GET | `/{order_id}/history` | `get_order_history` |
| POST | `/` | `create_order` |
| PUT | `/{order_id}` | `update_order` |
| DELETE | `/{order_id}` | `delete_order` |
| PATCH | `/{order_id}/status` | `update_order_status` |
| POST | `/bulk-status` | `bulk_update_order_status` |
| PATCH | `/{order_id}/payment` | `update_order_payment` |
| POST | `/{id_order}/returns` | `create_return` |
| GET | `/{id_order}/returns` | `get_order_returns` |
| GET | `/returns/get-return-by-id/{id}` | `get_return_by_id` |
| PUT | `/returns/{id}` | `update_return` |
| DELETE | `/returns/{id}` | `delete_return` |
| PUT | `/returns/details/{id}` | `update_return_detail` |
| DELETE | `/returns/details/{id}` | `delete_return_detail` |
| GET | `/returns/` | `get_all_returns` |
| POST | `/{order_id}/order_detail` | `add_order_detail` |
| PUT | `/{order_id}/order_detail/{id}` | `update_order_detail` |
| DELETE | `/{order_id}/order_detail/{id}` | `remove_order_detail` |

### OrderPackage - `/api/v1/order_packages`
CRUD standard: GET `/`, GET `/{id}`, POST `/`, PUT `/{id}`, DELETE `/{id}`

### OrderState - `/api/v1/order-states`
CRUD standard: GET `/`, GET `/{id}`, POST `/`, PUT `/{id}`, DELETE `/{id}`

### Payment - `/api/v1/payments`
CRUD standard: GET `/`, GET `/{id}`, POST `/`, PUT `/{id}`, DELETE `/{id}`

### Platform - `/api/v1/platforms`
CRUD standard: GET `/`, GET `/{id}`, POST `/`, PUT `/{id}`, DELETE `/{id}`

### PlatformStateTrigger - `/api/v1/platform-state-triggers`
| Metodo | Path | Funzione |
|---|---|---|
| GET | `/` | `get_platform_state_triggers` |
| GET | `/{trigger_id}` | `get_platform_state_trigger` |
| POST | `/` | `create_platform_state_trigger` |
| PUT | `/{trigger_id}` | `update_platform_state_trigger` |
| DELETE | `/{trigger_id}` | `delete_platform_state_trigger` |
| GET | `/events/list` | `get_available_events` |

### Preventivi - `/api/v1/preventivi`
| Metodo | Path | Funzione |
|---|---|---|
| POST | `/` | `create_preventivo` |
| GET | `/` | `get_preventivi` |
| GET | `/{id_order_document}` | `get_preventivo` |
| PUT | `/{id_order_document}` | `update_preventivo` |
| POST | `/{id_order_document}/articoli` | `add_articolo` |
| PUT | `/articoli/{id_order_detail}` | `update_articolo` |
| DELETE | `/articoli/{id_order_detail}` | `remove_articolo` |
| DELETE | `/{id_order_document}` | `delete_preventivo` |
| POST | `/{id_order_document}/duplicate` | `duplicate_preventivo` |
| POST | `/{id_order_document}/convert-to-order` | `convert_to_order` |
| POST | `/bulk-delete` | `bulk_delete_preventivi` |
| POST | `/bulk-convert-to-orders` | `bulk_convert_to_orders` |
| POST | `/bulk-remove-articoli` | `bulk_remove_articoli` |
| POST | `/bulk-update-articoli` | `bulk_update_articoli` |
| GET | `/{id_order_document}/download-pdf` | `download_preventivo_pdf` |

### Product - `/api/v1/products`
| Metodo | Path | Funzione |
|---|---|---|
| GET | `/` | `get_all_products` |
| GET | `/{product_id}` | `get_product_by_id` |
| POST | `/` | `create_product` |
| PUT | `/{product_id}` | `update_product` |
| DELETE | `/{product_id}` | `delete_product` |
| POST | `/{product_id}/upload-image` | `upload_product_image` |
| DELETE | `/{product_id}/image` | `delete_product_image` |
| GET | `/get-live-price/{id_origin}` | `get_live_price` |

### Role - `/api/v1/roles`
CRUD standard: GET `/`, GET `/{id}`, POST `/`, PUT `/{id}`, DELETE `/{id}`

### Sectional - `/api/v1/sectionals`
CRUD standard: GET `/`, GET `/{id}`, POST `/`, PUT `/{id}`, DELETE `/{id}`

### Shipping - `/api/v1/shippings`
CRUD standard: GET `/`, GET `/{id}`, POST `/`, PUT `/{id}`, DELETE `/{id}`

### Shipments - `/api/v1/shippings` (stesso prefix, tag diverso)
| Metodo | Path | Funzione |
|---|---|---|
| POST | `/{order_id}/create` | `create_shipment` |
| POST | `/bulk-create` | `bulk_create_shipments` |
| GET | `/{id_carrier_api}/tracking` | `get_tracking` |
| GET | `/download-label/{awb}` | `download_shipment_label` |
| DELETE | `/{order_id}/cancel` | `cancel_shipment` |
| POST | `/create-multi-shipments` | `create_multi_shipments` |
| GET | `/orders/{order_id}/shipment-status` | `get_order_shipment_status` |
| GET | `/orders/{order_id}/multi-shipments` | `get_order_multi_shipments` |

### ShippingState - `/api/v1/shipping-states`
CRUD standard: GET `/`, GET `/{id}`, POST `/`, PUT `/{id}`, DELETE `/{id}`

### Store - `/api/v1/stores`
| Metodo | Path | Funzione |
|---|---|---|
| GET | `/` | `get_all_stores` |
| GET | `/default` | `get_default_store` |
| GET | `/{store_id}` | `get_store_by_id` |
| POST | `/` | `create_store` |
| PUT | `/{store_id}` | `update_store` |
| DELETE | `/{store_id}` | `delete_store` |

### Sync - `/api/v1/sync`
| Metodo | Path | Funzione |
|---|---|---|
| POST | `/prestashop` | `sync_prestashop` |
| POST | `/prestashop/full` | `sync_prestashop_full` |
| GET | `/prestashop/status` | `get_prestashop_sync_status` |
| GET | `/prestashop/last-ids` | `get_prestashop_last_imported_ids` |
| POST | `/sync-images` | `sync_images` |
| POST | `/test-connection` | `test_prestashop_connection` |
| POST | `/prestashop/order-states` | `import_order_states_from_ecommerce` |
| POST | `/products/quantity` | `sync_products_quantity` |
| POST | `/products/price` | `sync_products_price` |
| POST | `/products/details` | `sync_products_details` |
| POST | `/orders/{order_id}/sync-state` | `sync_order_state_to_ecommerce` |

### Tax - `/api/v1/taxes`
CRUD standard: GET `/`, GET `/{id}`, POST `/`, PUT `/{id}`, DELETE `/{id}`

### User - `/api/v1/users`
| Metodo | Path | Funzione |
|---|---|---|
| GET | `/` | `get_all_users` |
| GET | `/{user_id}` | `get_user_by_id` |
| POST | `/` | `create_user` |
| PUT | `/{user_id}` | `update_user` |
| PUT | `/{user_id}/roles` | `update_user_roles` |
| DELETE | `/{user_id}` | `delete_user` |

**Totale: ~170+ endpoint su 36 router attivi**

---

## 20. Catalogo Completo dei Models

(Vedi sezione 5.4 per la tabella completa)

---

## 21. Catalogo Completo degli Schemas

| File Schema | Classi Principali |
|---|---|
| `address_schema.py` | `AddressSchema`, `AddressResponseSchema`, `AllAddressResponseSchema`, `AddressesByCustomerResponseSchema` |
| `app_configuration_schema.py` | `AppConfigurationSchema`, `CompanyInfoSchema`, `ElectronicInvoicingSchema`, `FatturapaSchema`, `EmailSettingsSchema`, `ApiKeysSchema` |
| `brand_schema.py` | `BrandSchema`, `BrandResponseSchema`, `AllBrandsResponseSchema` |
| `brt_configuration_schema.py` | `BrtConfigurationSchema`, `BrtConfigurationResponseSchema`, `BrtConfigurationUpdateSchema` |
| `brt_shipment_schema.py` | `BrtCreateShipmentResponse` |
| `carrier_api_schema.py` | `CarrierApiSchema`, `CarrierApiResponseSchema`, `CarrierApiUpdateSchema`, `AllCarriersApiResponseSchema` |
| `carrier_assignment_schema.py` | `CarrierAssignmentSchema`, `CarrierAssignmentUpdateSchema`, `CarrierAssignmentResponseSchema` |
| `carrier_price_schema.py` | `CarrierPriceSchema`, `CarrierPriceUpdateSchema`, `CarrierPriceResponseSchema` |
| `carrier_schema.py` | `CarrierSchema`, `CarrierResponseSchema`, `AllCarriersResponseSchema` |
| `category_schema.py` | `CategorySchema`, `CategoryResponseSchema`, `AllCategoryResponseSchema` |
| `company_fiscal_info_schema.py` | `CompanyFiscalInfoSchema`, `CompanyFiscalInfoUpdateSchema`, `CompanyFiscalInfoResponseSchema` |
| `country_schema.py` | `CountrySchema`, `CountryResponseSchema`, `AllCountryResponseSchema` |
| `customer_schema.py` | `CustomerSchema`, `CustomerResponseSchema`, `CustomerResponseWithoutAddressSchema`, `AllCustomerResponseSchema` |
| `ddt_schema.py` | `DDTDetailSchema`, `DDTResponseSchema`, `DDTCreatePartial*`, `DDTList*`, `DDTCreate*`, `DDTMerge*` |
| `dhl_configuration_schema.py` | `DhlConfigurationSchema`, `DhlConfigurationResponseSchema`, `DhlConfigurationUpdateSchema` |
| `dhl_shipment_schema.py` | `DhlCreateShipmentResponse`, nested request/response types |
| `dhl_tracking_schema.py` | `NormalizedTrackingEventSchema`, `NormalizedTrackingResponseSchema`, `DhlTrackingRequest/Response` |
| `fedex_configuration_schema.py` | `FedexConfigurationSchema`, `FedexConfigurationResponseSchema`, `FedexConfigurationUpdateSchema` |
| `fedex_shipment_schema.py` | `FedexShipmentRequestSchema`, `FedexShipmentResponseSchema` |
| `fiscal_document_schema.py` | `InvoiceCreateSchema`, `InvoiceResponseSchema`, `CreditNoteCreateSchema`, `FiscalDocumentResponseSchema`, `FiscalDocumentListResponseSchema` |
| `init_schema.py` | `InitDataSchema`, `CacheInfoSchema`, `PaymentInitSchema`, `ApiCarrierInitSchema`, `StoreInitSchema` |
| `lang_schema.py` | `LangSchema`, `LangResponseSchema`, `AllLangsResponseSchema` |
| `message_schema.py` | `MessageSchema`, `MessageResponseSchema`, `AllMessagesResponseSchema` |
| `order_detail_schema.py` | `OrderDetailSchema`, `OrderDetailResponseSchema`, `OrderDetailUpdateSchema`, `OrderDetailCreateSchema` |
| `order_document_schema.py` | `OrderDocumentSchema`, `OrderDocumentResponseSchema`, `AllOrderDocumentResponseSchema` |
| `order_history_schema.py` | `OrderHistorySchema` |
| `order_package_schema.py` | `OrderPackageSchema`, `OrderPackageResponseSchema`, `AllOrderPackagesResponseSchema` |
| `order_schema.py` | `OrderSchema`, `OrderUpdateSchema`, `OrderResponseSchema`, `AllOrderResponseSchema`, `BulkOrderStatusUpdateResponseSchema` |
| `order_state_schema.py` | `OrderStateSchema`, `OrderStateResponseSchema`, `AllOrdersStateResponseSchema` |
| `payment_schema.py` | `PaymentSchema`, `PaymentResponseSchema`, `AllPaymentsResponseSchema` |
| `platform_schema.py` | `PlatformSchema`, `PlatformResponseSchema`, `AllPlatformsResponseSchema` |
| `platform_state_trigger_schema.py` | `PlatformStateTriggerSchema`, `PlatformStateTriggerUpdateSchema`, `PlatformStateTriggerResponseSchema` |
| `preventivo_schema.py` | `PreventivoCreateSchema`, `PreventivoUpdateSchema`, `PreventivoResponseSchema`, `PreventivoListResponseSchema`, `PreventivoStatsSchema` |
| `product_schema.py` | `ProductSchema`, `ProductResponseSchema`, `ProductUpdateSchema`, `AllProductsResponseSchema` |
| `return_schema.py` | `ReturnCreateSchema`, `ReturnUpdateSchema`, `ReturnDetailUpdateSchema`, `AllReturnsResponseSchema` |
| `role_schema.py` | `RoleSchema`, `RoleResponseSchema`, `AllRolesResponseSchema` |
| `sectional_schema.py` | `SectionalSchema`, `SectionalResponseSchema`, `AllSectionalsResponseSchema` |
| `shipment_schema.py` | `BulkShipmentCreateRequestSchema`, `BulkShipmentCreateResponseSchema` |
| `shipping_schema.py` | `ShippingSchema`, `ShippingUpdateSchema`, `ShippingResponseSchema`, `AllShippingResponseSchema`, `MultiShippingDocument*`, `OrderShipmentStatus*` |
| `shipping_state_schema.py` | `ShippingStateSchema`, `ShippingStateResponseSchema`, `AllShippingStatesResponseSchema` |
| `store_schema.py` | `StoreSchema`, `StoreCreateSchema`, `StoreUpdateSchema`, `StoreResponseSchema`, `AllStoresResponseSchema` |
| `tax_schema.py` | `TaxSchema`, `TaxResponseSchema`, `AllTaxesResponseSchema` |
| `user_schema.py` | `UserSchema`, `UserResponseSchema`, `AllUsersResponseSchema`, `UserRolesUpdateSchema`, `Token`, `ChangePasswordSchema` |

---

## 22. Convenzioni e Pattern Ricorrenti

### 22.1 Naming

| Elemento | Convenzione | Esempio |
|---|---|---|
| Tabelle DB | snake_case plurale | `orders`, `fiscal_documents` |
| PK | `id_<entity_singular>` | `id_order`, `id_customer` |
| FK | `id_<referenced_entity>` | `id_store`, `id_platform` |
| Model class | PascalCase singolare | `Order`, `FiscalDocument` |
| Repository | `<Entity>Repository` | `OrderRepository` |
| Interface | `I<Entity>Repository` | `IOrderRepository` |
| Service | `<Entity>Service` | `OrderService` |
| Schema | `<Entity>Schema` | `OrderSchema` |
| Router file | snake_case singolare | `order.py`, `fiscal_documents.py` |
| Router prefix | `/api/v1/<plurale>` | `/api/v1/orders` |

### 22.2 Pattern CRUD Standard

La maggior parte delle entita' segue questo pattern:

```
router.py          → Service call via container.resolve_with_session()
  ↓
service.py         → Business logic + @emit_event_on_success
  ↓
repository.py      → BaseRepository CRUD + query custom
  ↓
model.py           → SQLAlchemy ORM
  ↓
schema.py          → Pydantic input/output
```

### 22.3 Response Pattern

- **Singola entita':** `{"status": "success", "data": {...}}`
- **Lista paginata:** `{"status": "success", "count": N, "data": [...]}`
- **Errore:** `{"error_code": "...", "message": "...", "details": {...}, "status_code": N}`

### 22.4 Multi-tenancy

- Store-based: molte entita' hanno `id_store` per supportare multi-negozio
- Platform-based: `Store` → `Platform` per supportare piu' piattaforme e-commerce
- Cache: supporto `tenant_from_user` nel decoratore `@cached`

---

## 23. Mappa delle Dipendenze tra Moduli

### 23.1 Moduli Core (utilizzati ovunque)

```
core/exceptions.py  ← Tutti i service e repository
core/interfaces.py  ← Tutti i repository e service interface
core/container.py   ← Tutti i router (resolve_with_session)
core/settings.py    ← Cache, middleware, carrier clients
database.py         ← Tutti i repository (Session, Base)
```

### 23.2 Dipendenze tra Entita' Business

```
Platform → Store → [Order, Product, Customer, Address, Carrier, ...]
Order → Customer, Address (delivery/invoice), Carrier, Shipping, Platform, Store
Order → OrderDetail → Product, Tax
Order → OrderDocument → Sectional, Shipping, Payment
Order → FiscalDocument → FiscalDocumentDetail → Tax
Carrier → CarrierApi → [BrtConfig, DhlConfig, FedexConfig]
Carrier → CarrierAssignment
Carrier → CarrierPrice
User → Role (M2M via user_roles)
OrderState ↔ Order (M2M via orders_history)
```

### 23.3 Dipendenze Service

```
OrderService → OrderRepository, CustomerRepository, ProductRepository, ...
ShipmentService → CarrierServiceFactory → [BrtShipmentService, DhlShipmentService, FedexShipmentService]
SyncService → create_ecommerce_service() → PrestaShopService → [CustomerRepo, ProductRepo, ...]
FiscalDocumentService → FatturaPAService → FatturaPAValidator
PDFServices → [Repository vari per dati]
```

---

## 24. Linee Guida per Prompt Generici

### 24.1 Contesto da Fornire Sempre

Quando si crea un prompt per lavorare su questo progetto, includere SEMPRE:

1. **Stack:** FastAPI + SQLAlchemy 2.0 + Pydantic v2 + MySQL
2. **Architettura:** Layer Router → Service → Repository → Model con DI custom
3. **Pattern:** `container.resolve_with_session(IInterface, db_session)` per iniettare dipendenze
4. **Eccezioni:** Usare la gerarchia `BaseApplicationException` (`NotFoundException`, `BusinessRuleException`, `ValidationException`, etc.)
5. **Eventi:** `@emit_event_on_success` con `EventType` per operazioni CUD
6. **Cache:** Decoratore `@cached` con `TTL_PRESETS` per operazioni di lettura
7. **Pydantic v2:** `from_attributes = True`, `model_dump()`, `model_validate()`
8. **Base Repository:** Estendere `BaseRepository<T, K>` per nuove entita'
9. **Convenzioni PK:** `id_<entity_name>` (es. `id_order`, `id_product`)
10. **Registrazione DI:** Aggiungere coppie interfaccia/implementazione in `container_config.py`

### 24.2 Template Prompt Generico

```
Sei un esperto sviluppatore Python/FastAPI che lavora su ECommerceManagerAPI.

L'applicazione usa:
- FastAPI 0.110.1 come framework web
- SQLAlchemy 2.0 come ORM con MySQL
- Pydantic v2 per validazione e serializzazione
- Architettura a layer: Router → Service → Repository → Model
- Dependency Injection custom con Container (resolve_with_session)
- Sistema eventi asincrono con EventBus e @emit_event_on_success
- Cache ibrida Redis + Memory con decoratore @cached
- Eccezioni tipizzate (NotFoundException, BusinessRuleException, etc.)

Convenzioni del progetto:
- PK: id_<entity> (es. id_order)
- Tabelle: snake_case plurale
- Router prefix: /api/v1/<entity_plural>
- Ogni entita' ha: model, repository (+ interface), service (+ interface), schema, router
- I repository estendono BaseRepository<T, K>
- I service implementano interfacce ABC da src/services/interfaces/
- Le dipendenze vanno registrate in src/core/container_config.py

[INSERIRE TASK SPECIFICO QUI]
```

---

## 25. Template per Prompt Specifici per Modulo

### 25.1 Per Nuova Entita' CRUD

```
Crea una nuova entita' [NOME] seguendo il pattern del progetto:

File da creare:
1. src/models/[nome].py - SQLAlchemy model con tabella [nome_plurale], PK id_[nome]
2. src/schemas/[nome]_schema.py - Schema Pydantic (base, response, update, all_response)
3. src/repository/interfaces/[nome]_repository_interface.py - Interfaccia I[Nome]Repository
4. src/repository/[nome]_repository.py - Implementazione che estende BaseRepository
5. src/services/interfaces/[nome]_service_interface.py - Interfaccia I[Nome]Service
6. src/services/routers/[nome]_service.py - Implementazione service con business logic
7. src/routers/[nome].py - Router FastAPI con CRUD (GET list, GET by id, POST, PUT, DELETE)

File da modificare:
- src/models/__init__.py - Aggiungere import
- src/core/container_config.py - Registrare repository e service
- src/main.py - Registrare il router

Segui le convenzioni: [vedi sezione 22]
```

### 25.2 Per Modifica Entita' Esistente

```
Modifica l'entita' [NOME] nel progetto ECommerceManagerAPI.

File coinvolti:
- Model: src/models/[nome].py
- Schema: src/schemas/[nome]_schema.py
- Repository: src/repository/[nome]_repository.py (interface: interfaces/[nome]_repository_interface.py)
- Service: src/services/routers/[nome]_service.py (interface: interfaces/[nome]_service_interface.py)
- Router: src/routers/[nome].py

Contesto: [descrizione tabella, relazioni, endpoint esistenti]

Task: [modifica richiesta]
```

### 25.3 Per Integrazione Corriere

```
Integra un nuovo corriere [NOME] nel sistema di spedizioni.

Architettura corrieri esistente:
- Client HTTP: src/services/ecommerce/shipments/[nome]_client.py
- Mapper request/response: src/services/ecommerce/shipments/[nome]_mapper.py
- Mapping stati: src/services/ecommerce/shipments/[nome]_status_mapping.py
- Schema: src/schemas/[nome]_shipment_schema.py + [nome]_configuration_schema.py
- Service: src/services/routers/[nome]_shipment_service.py + [nome]_tracking_service.py
- Config model: src/models/[nome]_configuration.py
- Factory: src/factories/services/carrier_service_factory.py (aggiungere branch)
- Container: src/core/container_config.py (registrare client, mapper, service)

Pattern da seguire: DHL o BRT come riferimento.
```

### 25.4 Per Plugin Evento

```
Crea un nuovo plugin [NOME] per il sistema eventi.

Directory: src/events/plugins/[nome]/
File necessari:
- __init__.py
- plugin.py (classe che estende EventHandlerPlugin, metodo get_plugin())
- handlers.py (handler che estende BaseEventHandler)
- requirements.txt (dipendenze extra)

Registrazione: config/event_handlers.yaml

Pattern da seguire: email_notification o platform_state_sync come riferimento.
```

### 25.5 Per Sync E-commerce

```
[Estendi/Modifica] la sincronizzazione e-commerce.

Architettura sync:
- Base: src/services/ecommerce/base_ecommerce_service.py (ABC, async context manager)
- PrestaShop: src/services/ecommerce/prestashop_service.py
- Factory: src/services/ecommerce/service_factory.py
- Router: src/routers/sync.py (endpoint /api/v1/sync/*)
- Task periodici: src/services/sync/

Per aggiungere una nuova piattaforma: implementare BaseEcommerceService e registrare in service_factory.py
```

### 25.6 Per Sistema Fiscale

```
[Modifica/Estendi] il sistema documenti fiscali.

File coinvolti:
- Model: src/models/fiscal_document.py, fiscal_document_detail.py
- Schema: src/schemas/fiscal_document_schema.py
- Service: src/services/routers/fiscal_document_service.py
- Router: src/routers/fiscal_documents.py
- XML FatturaPA: src/services/external/fatturapa_service.py
- Validazione: src/services/external/fatturapa_validator.py
- PDF: src/services/pdf/fiscal_document_pdf_service.py

Flusso fatturazione: Ordine → Fattura → XML FatturaPA → Upload SDI → Monitoraggio
```

---

## Note Finali

### Aree di Attenzione / Debito Tecnico Identificato

1. **OrderDetail senza FK ORM**: `id_order`, `id_product`, `id_tax` sono integer senza `ForeignKey()` / `relationship()` - relazioni solo logiche
2. **Shipping senza FK ORM**: `id_carrier_api`, `id_shipping_state`, `id_tax` sono plain integer
3. **CSV Import bug potenziale**: `ImportResult` usa `id_platform` non definito nello scope (riga ~180)
4. **query_utils type hint**: `search_in_every_field` ha annotazione `Query` da FastAPI invece di SQLAlchemy query
5. **CacheContext sync/async mismatch**: `invalidate_on_commit` usa `with CacheContext` sincrono ma `CacheContext` ha metodi async
6. **FatturaPAValidator debug log**: scrive su file `.cursor/debug.log` (codice debug rimasto)
7. **IUnitOfWork**: interfaccia definita ma non implementata nel progetto
8. **Alembic versions**: directory gitignored, migrazioni locali

### Statistiche Progetto

| Metrica | Valore |
|---|---|
| File Python totali (src/) | ~380 |
| Modelli database | 40 (38 entita' + 2 tabelle associative) |
| Repository | ~37 + ~37 interfacce |
| Service | ~41 + ~38 interfacce |
| Router | 36 moduli attivi |
| Schema | 44 moduli |
| Endpoint API | ~170+ |
| Eventi definiti | 16+ tipi |
| Plugin | 3 installati |
| Corrieri integrati | 3 (BRT, DHL, FedEx) |
| Test file | ~15+ |
| Documentazione | 10+ file markdown |
| Dipendenze Python | 73 pacchetti |
