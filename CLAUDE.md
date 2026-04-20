# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Elettronew API** — a centralized FastAPI backend for e-commerce operations: order management, multi-carrier shipping (BRT, DHL, FedEx), fiscal documents (FatturaPA/SDI), DDT, quotes, PrestaShop sync, and PDF generation.

## Commands

```bash
# Setup
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
copy env.example .env
python scripts/setup_initial.py
alembic upgrade head

# Run
.\run_dev.ps1                                          # dev (hot reload)
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000  # manual

# Test
pytest
pytest -v test/routers/test_product.py                 # single file
pytest --cov=src --cov-report=html

# Lint / format
make lint      # flake8 + black check + isort check
make format    # black + isort

# Database
alembic upgrade head
alembic revision --autogenerate -m "description"
make db-seed

# Docker (full stack with Redis, Prometheus, Grafana)
make up / make down
```

API docs at http://localhost:8000/docs after starting.

## Architecture

### Layer Stack (always follow this order)

```
Router → Service → Repository → SQLAlchemy Model → MySQL
```

- **Routers** (`src/routers/`) — FastAPI endpoint definitions, Pydantic validation, JWT auth, DI resolution
- **Services** (`src/services/routers/`) — business logic; `src/services/ecommerce/` for PrestaShop; `src/services/sync/` for background tasks
- **Repositories** (`src/repository/`) — data access via `BaseRepository<T, K>`; interfaces in `src/repository/interfaces/`
- **Models** (`src/models/`) — SQLAlchemy ORM; naming: PascalCase class, snake_case table, `id_<entity>` PKs
- **Schemas** (`src/schemas/`) — Pydantic v2 DTOs: `*Schema` (input), `*ResponseSchema` (output), `*CreateSchema`, `*UpdateSchema`

### Dependency Injection

Custom `Container` in `src/core/container.py`. All service/repository bindings registered in `src/core/container_config.py`. Always resolve via:
```python
service = container.resolve_with_session(IService, db)
```
Never instantiate services or repositories directly in routers.

### Key Infrastructure

| Component | Location | Notes |
|-----------|----------|-------|
| DI Container | `src/core/container.py` + `container_config.py` | singleton/transient registration |
| Exception hierarchy | `src/core/exceptions.py` | `BaseApplicationException` → 400-500 with `error_code` |
| Cache (hybrid Redis+memory) | `src/core/cache.py` | `@cached` decorator, TTL presets: short=60s, medium=3600s, long=86400s |
| Event bus | `src/events/core/event_bus.py` | async `subscribe/publish`; use `@emit_event_on_success` on service methods |
| Plugin system | `src/events/` + `config/event_handlers.yaml` | circuit-breaker protected (5 failures/5min) |
| Settings | `src/core/settings.py` | Pydantic settings, feature flags for cache per resource |

### Authentication

- JWT (HS256) via `SECRET_KEY` env var, 30-day tokens
- `OAuth2PasswordBearer` scheme; `get_current_user()` dependency in routes
- RBAC: users have `roles` (many-to-many with `Role`); `authorize()` decorator for checks
- Login: `POST /api/v1/auth/login`

### Middleware Stack (registration order in `main.py`)

1. CORS
2. `ErrorLoggingMiddleware`
3. `PerformanceLoggingMiddleware` (slow threshold: 1.0s, adds `X-Process-Time`)
4. `SecurityLoggingMiddleware`
5. `ConditionalMiddleware` — ETag + `If-None-Match` support, `Cache-Control` headers (TTL 300s default)

### Carrier / E-commerce Strategy Pattern

- Carriers: `CarrierServiceFactory` resolves BRT/DHL/FedEx strategies
- E-commerce: `create_ecommerce_service()` factory; PrestaShop is current implementation
- Add new carriers/platforms by implementing the corresponding interface and registering in the factory

## Naming Conventions

- SQLAlchemy models: `PascalCase`, tables: `snake_case`, PKs: `id_<entity>`
- Pydantic schemas: `*Schema`, `*ResponseSchema`, `*CreateSchema`, `*UpdateSchema`
- Service interfaces: `I*Service` (ABC in `src/services/interfaces/`)
- Repository interfaces: `I*Repository` (ABC in `src/repository/interfaces/`)
- API prefix: `/api/v1/<resource>`
