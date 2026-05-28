# ECommerceManagerAPI

API REST per ordini, resi, documenti fiscali, spedizioni e sincronizzazione e-commerce (PrestaShop).

---

## Requisiti

- **Python 3.10+**
- **MySQL**
- (Opzionale) Redis per cache

---

## Installazione dipendenze

```bash
# Dalla root del progetto
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

# Installa le dipendenze
pip install -r requirements.txt
```

---

## Configurazione

Copia il file ambiente e imposta le variabili (database e JWT):

```bash
# Windows
copy env.example .env

# Linux / macOS
cp env.example .env
```

Modifica `.env` con almeno:

- `DATABASE_MAIN_USER`, `DATABASE_MAIN_PASSWORD`, `DATABASE_MAIN_ADDRESS`, `DATABASE_MAIN_PORT`, `DATABASE_MAIN_NAME`
- `SECRET_KEY` (per JWT)

Applica le migrazioni al database:

```bash
alembic upgrade head
```

---

## Esecuzione script

**Setup iniziale** (Order State, Shipping State, App Configuration, Platform, Store, Role, utente admin, CompanyFiscalInfo, colonna `orders.vies_status`, seed IVA UE):

```bash
python scripts/setup_initial.py
```

Lo script è **idempotente**: aggiunge `vies_status` su `orders` se assente e crea/aggiorna i `Tax` default per i 27 paesi UE (`Tax.id_country` + `is_default=1`). Richiede che la tabella `countries` contenga i codici ISO corrispondenti (es. da sync PrestaShop).

Altri script utili:

```bash
# Solo configurazioni app
python scripts/init_app_configurations.py

# Warm cache (se usi cache)
python scripts/warm_cache.py
```

---

## Avvio applicazione

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

- **API**: http://localhost:8000  
- **Swagger**: http://localhost:8000/docs  
- **Health**: http://localhost:8000/api/v1/health (se esposto)

---

## API — Default IVA per paese (VIES Fase 1)

Prefisso esistente `/api/v1/taxes`. Permessi RBAC: modulo `settings`, azioni `read` / `update`.

| Metodo | Path | Descrizione |
|--------|------|-------------|
| GET | `/api/v1/taxes/country-defaults` | Lista `Tax` con `is_default=1` per paese |
| GET | `/api/v1/taxes/country-defaults/{iso_code}` | Default per paese (es. `IT`) |
| PUT | `/api/v1/taxes/{id_tax}/set-country-default` | Imposta unico default per `id_country` del Tax |

Il payload `/api/v1/init/` espone già `taxes[]` con `id_country` e `is_default` (nessuna chiave aggiuntiva).

---

## API — VIES ordini (BE-VIES-2, Fase 2/4)

Prefisso `/api/v1/orders`. Permessi RBAC: `orders.read` (filtro lista), `orders.update` (esenzione).

| Metodo | Path | Descrizione |
|--------|------|-------------|
| GET | `/api/v1/orders/?vies_status=eligible\|not_eligible\|null` | Filtro snapshot VIES (`null` = solo `vies_status` IS NULL; assenza param = tutti) |
| PATCH | `/api/v1/orders/{id}/apply-vies-exemption` | Applica esenzione: righe a 0% IVA, totale ivato invariato, `vies_status=eligible` |
| POST | `/api/v1/orders/bulk-apply-vies-exemption` | Stessa logica su `{ "order_ids": [1,2,...] }` in transazione atomica |

Ricalcolo BE: `calculate_price_without_tax` (righe) + `OrderService.recalculate_totals_for_order` (totali ordine).

Evento: `ORDER_VIES_EXEMPTION_APPLIED`.

Sync PrestaShop: `src/services/vies/vies_status_resolver.py` — snapshot `vies_status` senza chiamate VIES runtime.

---

## Ultime modifiche (2026-05-27) — BE-VIES-CLEANUP-SEED

**Scope:** Rimozione seed aliquote UE (BE-VIES-1) da prod/stage.

- Seed disattivato in `scripts/setup_initial.py` (attivo solo con `SEED_EU_VAT_TAXES=1` per test/CI).
- Logica seed/cleanup: `src/vies/eu_vat_seed.py`.
- Migration: `alembic upgrade head` → `20260527_0001_cleanup_be_vies_1_seed`.
- Guida: [docs/BE_VIES_CLEANUP_SEED.md](docs/BE_VIES_CLEANUP_SEED.md).

## Ultime modifiche (2026-05-27) — BE-VIES-2

**Scope:** Fase 2/4 VIES — sync PrestaShop + API gestionale.

- **Sync:** `vies_status_resolver` + bulk INSERT in `prestashop_service`; P.IVA da `vat_number` o `vat`.
- **Lista:** query param `vies_status` su `GET /api/v1/orders/`.
- **Esenzione manuale:** `PATCH .../apply-vies-exemption`, `POST .../bulk-apply-vies-exemption`, evento `ORDER_VIES_EXEMPTION_APPLIED`.
- **Test:** `tests/unit/repository/test_order_repository_vies_filter.py`, `tests/unit/services/test_order_vies_exemption.py`, `tests/integration/api/v1/test_order_vies_exemption.py`.

## Ultime modifiche (2026-05-27) — BE-VIES-1

**Scope:** Fondamenta dati VIES — Fase 1/4.

- **Order:** enum `ViesStatus` (`eligible` \| `not_eligible`) + colonna nullable `vies_status` (popolamento in Fase 2 sync PrestaShop).
- **Tax:** riuso `Tax(id_country, is_default)` per default IVA per paese; endpoint `country-defaults`; evento `TAX_COUNTRY_DEFAULT_CHANGED`; invalidazione cache `init_data:static` / `init_data:full` su `set-country-default`.
- **Setup:** `scripts/setup_initial.py` — DDL `vies_status` + seed 27 aliquote UE (FI a 25% per limite `Tax.percentage` Integer).
- **Test:** `tests/unit/repository/test_tax_repository.py`, `tests/unit/services/test_tax_service.py`, `tests/integration/api/v1/test_tax_country_defaults.py`, `tests/scripts/test_setup_initial_eu_taxes.py`.

---

## Documentazione

- [DOCUMENTAZIONE.md](DOCUMENTAZIONE.md) – panoramica e architettura  
- [QUICK_START.md](QUICK_START.md) – avvio rapido e comandi  
- [docs/](docs/) – guide specifiche (eventi, plugin, sync, ecc.)
