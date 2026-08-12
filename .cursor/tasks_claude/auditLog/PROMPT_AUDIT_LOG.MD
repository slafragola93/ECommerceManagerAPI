Sei un esperto sviluppatore Python/FastAPI che lavora su **ECommerceManagerAPI** (nome interno: Elettronew API).

## Stack e architettura del progetto
- FastAPI 0.110.1, SQLAlchemy 2.0 (MySQL via PyMySQL), Pydantic v2, Alembic per le migrazioni
- Architettura a layer: `Router → Service → Repository → Model`
- Dependency Injection custom: `container.resolve_with_session(IInterface, db_session)`
- Sistema eventi asincrono: `EventBus` + decoratore `@emit_event_on_success(event_type=..., data_extractor=..., metadata_extractor=...)`, gestito da `src/events/core/`, `src/events/runtime.py`
- Cache ibrida Redis+Memory con decoratore `@cached` (NON va usata sui dati di audit: sono log "live")
- Eccezioni tipizzate: `NotFoundException`, `BusinessRuleException`, `ValidationException`, `AuthorizationException`, ecc. da `src/core/exceptions.py`
- Auth: JWT (python-jose) + `OAuth2PasswordBearer`, dependency `get_current_user`
- RBAC esistente: model `User` ↔ `Role` (M2M via `user_roles`), permessi gestiti come stringhe dot-notation (es. `users.view`, `permissions.manage`) consumate anche dal frontend Angular

Convenzioni del progetto (rispettarle sempre):
- PK: `id_<entity_singolare>` (es. `id_order`, `id_audit_log`)
- Tabelle DB: snake_case plurale
- Router prefix: `/api/v1/<entity_plurale>`
- Ogni entità ha: model, repository (+ interfaccia `I<Entity>Repository`), service (+ interfaccia `I<Entity>Service`), schema, router
- I repository estendono `BaseRepository<T, K>` (`src/core/base_repository.py`)
- I service implementano interfacce ABC da `src/services/interfaces/`
- Le dipendenze vanno registrate in `src/core/container_config.py`
- Risposte: singola entità `{"status": "success", "data": {...}}`, lista `{"status": "success", "count": N, "data": [...]}`, errore `{"error_code": "...", "message": "...", "details": {...}, "status_code": N}`

## Contesto del task

Il progetto oggi **non ha alcun sistema di audit log** (nessun model, nessun endpoint). Il frontend Angular ha già uno scaffold (interceptor, store NgRx, componente di visualizzazione) ma è "orfano": non esiste ancora nessuna persistenza server-side da cui leggere. Il tuo compito è costruire la parte backend.

Il progetto ha già un `EventBus` che riceve un evento per quasi ogni operazione di creazione/modifica/cancellazione (16+ `EventType`: `ORDER_CREATED`, `CUSTOMER_UPDATED`, `PRODUCT_DELETED`, ecc.), emessi via `@emit_event_on_success` da quasi tutti i service. **Non instrumentare manualmente ogni service**: la scrittura del log di audit deve avvenire tramite un subscriber dedicato dell'EventBus, non tramite chiamate sparse nei service esistenti.

## Cosa implementare

### 1. Entità `AuditLog`

File da creare, seguendo esattamente il pattern CRUD standard del progetto:

- `src/models/audit_log.py` — SQLAlchemy model, tabella `audit_logs`, PK `id_audit_log`. Colonne:
  - `timestamp` (datetime UTC, indicizzato)
  - `actor_id` (int, nullable — nullable per azioni di sistema/anonime tipo login fallito)
  - `actor_username` (str) e `actor_role` (str) — **snapshot al momento dell'azione**, non FK risolta a runtime, per sopravvivere a cancellazione/modifica utente
  - `action` (str, es. `"order.create"`, `"auth.login"`, `"user.roles_update"`)
  - `resource_type` (str), `resource_id` (str, nullable)
  - `changes` (JSON, nullable) — `{"before": {...}, "after": {...}}`
  - `level` (str/enum: `standard` | `sensitive` | `security`)
  - `ip_address` (str, nullable), `request_id` (UUID str, per correlazione coi log tecnici del middleware)
  - `status` (str: `success` | `failure`)
  - Indici compositi: `(timestamp, actor_id)`, `(resource_type, resource_id)`, `(level, timestamp)`
  - **Tabella append-only**: nessun meccanismo di update/delete previsto a livello applicativo
- `src/schemas/audit_log_schema.py` — `AuditLogResponseSchema`, `AllAuditLogResponseSchema` (lista paginata con count). Non serve uno schema di input pubblico: il log non si crea via API REST esposta ai client, solo internamente.
- `src/repository/interfaces/audit_log_repository_interface.py` — `IAuditLogRepository(IRepository[AuditLog, int])`
- `src/repository/audit_log_repository.py` — estende `BaseRepository[AuditLog, int]`, implementa `get_all(offset, limit, actor_id=None, resource_type=None, resource_id=None, action=None, level=None, date_from=None, date_to=None)` usando gli helper esistenti in `src/services/core/query_utils.py` (`filter_by_id`, `filter_by_string`, `filter_by_date`, `search_in_every_field`)
- `src/services/interfaces/audit_log_service_interface.py` — `IAuditLogService(IBaseService)` con `get_all(scope, filters)` e `get_by_id(id)`
- `src/services/routers/audit_log_service.py` — implementazione. Contiene la **logica di visibilità/scope** (vedi sezione permessi sotto): riceve un oggetto scope risolto dal router (basato sui permessi dell'utente corrente) e applica il filtro `actor_id` obbligatorio se l'utente non ha il permesso "vedi tutto".
- `src/routers/audit_log.py` — prefix `/api/v1/audit-logs`, solo endpoint di lettura:
  - `GET /` — lista paginata con filtri via query params (offset, limit, actor_id, resource_type, resource_id, action, level, date_from, date_to)
  - `GET /{id_audit_log}` — dettaglio singolo (include `changes` completo)
  - Nessun POST/PUT/DELETE esposto.

File da modificare:
- `src/models/__init__.py` — import del nuovo model
- `src/core/container_config.py` — registrare `IAuditLogRepository → AuditLogRepository` e `IAuditLogService → AuditLogService`
- `src/main.py` — registrare il router
- `alembic/` — generare la migrazione per la nuova tabella

### 2. Cattura dell'evento — subscriber EventBus dedicato

Crea un modulo (es. `src/services/audit/audit_log_handler.py` o dentro `src/events/`) che:

1. Si iscrive a `EventBus` per un elenco curato di `EventType` esistenti (praticamente tutti quelli CUD già definiti: ordini, spedizioni, documenti, clienti, prodotti, indirizzi, sync, import CSV) più eventuali nuovi tipi (vedi punto 3).
2. **Non va registrato come plugin** in `src/events/plugins/` — è infrastruttura core, non deve essere soggetto al circuit breaker pensato per i plugin di terze parti (5 failure → disabilitato per 5 minuti: inaccettabile per l'audit). Registralo direttamente come subscriber all'avvio dell'app (es. in `main.py` o in un modulo di startup dedicato), analogamente a come vengono registrati gli handler core.
3. Per ogni evento ricevuto: legge `event.data` per ricavare `resource_type`/`resource_id`, legge `event.metadata` per ricavare l'attore (vedi punto successivo), determina il `level` in base al tipo di evento, e scrive la riga in `audit_logs` aprendo una propria sessione DB (`SessionLocal()`), **non** riusando la sessione della request (l'handler gira in modo disaccoppiato via `asyncio.gather`).
4. Gestione errori: try/except attorno alla scrittura, log dell'errore ma **nessuna propagazione** — un fallimento nella scrittura dell'audit non deve mai far fallire la request principale né bloccare altri handler.

### 3. Propagazione dell'attore (chi ha fatto l'azione)

Serve rendere disponibile `{user_id, username, roles, request_id, ip_address}` all'interno dell'handler dell'evento, che gira fuori dal ciclo di vita della request HTTP.

- Aggiungi un `ContextVar` (stesso pattern di `CorrelationTracker` in `src/core/observability.py`) che viene popolato nella dependency `get_current_user` (o subito dopo la validazione JWT) con i dati dell'utente autenticato, e da `ErrorLoggingMiddleware` con `request_id`/`ip_address`.
- Estendi il comportamento di `@emit_event_on_success` (o il punto in cui viene costruito `Event.metadata`) in modo che il metadata dell'evento includa **sempre** questi dati letti dal ContextVar, senza dover modificare ogni singola chiamata a `metadata_extractor` nei service esistenti — deve essere un arricchimento automatico e trasparente.
- Per le azioni di sistema (es. sync periodici, job schedulati) l'attore sarà `None`/`"system"`: gestiscilo esplicitamente.

### 4. Eventi non coperti dal sistema esistente

Alcune azioni rilevanti per l'audit non emettono oggi nessun evento. Aggiungi nuovi `EventType` (nello stesso enum in `src/events/core/event.py`) ed emettili con `@emit_event_on_success` nei punti indicati, seguendo lo stesso pattern già in uso:

- `AUTH_LOGIN_SUCCESS`, `AUTH_LOGIN_FAILED` — in `src/services/routers/auth_service.py` (o dove risiede la logica di login)
- `AUTH_LOGOUT`
- `USER_ROLES_UPDATED` — nel service dietro `PUT /api/v1/users/{user_id}/roles`
- `FISCAL_DOCUMENT_SENT_TO_SDI` — se non già coperto da un evento documento generico
- `DOCUMENT_PDF_GENERATED` / `DOCUMENT_EXPORTED` — generazione PDF (DDT, fatture, preventivi) ed export fatture (`/fiscal_documents/invoices/export`)

Questi vanno inclusi anche nella lista di sottoscrizione dell'handler di audit (punto 2) e mappati a `level = "security"` (auth, ruoli) o `level = "sensitive"` (documenti fiscali, export).

### 5. Livelli di visibilità (RBAC — riuso di quanto esiste, non un sistema nuovo)

Non introdurre un nuovo meccanismo di permessi: il progetto ne ha già uno (model `Role`, M2M `user_roles`, permessi dot-notation letti anche dal frontend). Aggiungi due nuove chiavi di permesso al set esistente:

- `audit.view` — l'utente vede solo gli audit log dove `actor_id == current_user.id`
- `audit.view_all` — l'utente vede tutti gli audit log, senza filtro per attore

Nel router, risolvi lo scope leggendo i permessi dell'utente corrente (stesso meccanismo usato per proteggere `/users` e `/roles`) e passalo al service. Se l'utente non ha nessuno dei due permessi → `AuthorizationException` (403). Il `level = "security"` (login, cambio ruoli) dovrebbe essere visibile solo a chi ha `audit.view_all` indipendentemente dall'attore, anche per azioni proprie — valuta se serve un terzo permesso `audit.view_security` o se basta vincolarlo ad `audit.view_all`; motiva la scelta nel codice con un commento.

Mappa dei livelli suggerita (adattala se necessario):
- `standard`: CUD su ordini, prodotti, clienti, indirizzi, preventivi, DDT
- `sensitive`: documenti fiscali, export, generazione PDF, sync e-commerce
- `security`: login/logout, cambio ruoli/permessi, azioni su utenti

### 6. Test

Segui le convenzioni della suite esistente (`pytest`, fixtures in `tests/conftest.py`, `EventBusSpy`, ruoli pre-configurati admin/ordini/user):

- Aggiungi una factory `tests/factories/audit_log.py`
- `tests/integration/api/v1/test_audit_logs.py`: verifica che un'azione CUD (es. creazione ordine) produca effettivamente una riga di audit con actor/level corretti; verifica lo scoping per ruolo (`audit.view` vs `audit.view_all`); verifica che un fallimento nella scrittura dell'audit non faccia fallire la request principale (usa `EventBusSpy` o mock della sessione)
- Test unitario sul subscriber: dato un `Event` con metadata di attore, verifica che venga scritta la riga corretta

## Output atteso

Elenca tutti i file creati/modificati, mostra il contenuto completo dei file nuovi, e per i file modificati mostra solo le porzioni cambiate con contesto sufficiente per applicare la modifica manualmente. Segnala esplicitamente eventuali decisioni architetturali che hai dovuto prendere (es. gestione del terzo permesso `audit.view_security`, elenco esatto degli `EventType` sottoscritti) motivandole brevemente.
