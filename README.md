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

Guida FE: [docs/FE_VIES_APPLY_EXEMPTION_BUTTON.md](docs/FE_VIES_APPLY_EXEMPTION_BUTTON.md) — prompt chat FE: [.cursor/tasks_claude/prompt_FE_vies_apply_exemption.md](.cursor/tasks_claude/prompt_FE_vies_apply_exemption.md).

Ricalcolo BE: `calculate_price_without_tax` (righe) + `OrderService.recalculate_totals_for_order` (totali ordine).

Evento: `ORDER_VIES_EXEMPTION_APPLIED`.

Sync PrestaShop: `src/services/vies/vies_status_resolver.py` — snapshot `vies_status` senza chiamate VIES runtime né riscrittura aliquote in import.

**Logica VIES attiva solo su:**
- `PATCH /api/v1/orders/{id}/apply-vies-exemption` (rettifica manuale KO → OK; usa `reverse_charge_id_tax` da settings se configurato)
- `POST /api/v1/orders` con `vies_status: eligible` esplicito — righe senza `id_tax` ricevono l’aliquota VIES configurata

Helper: `src/vies/tax_resolution.py` (`get_vies_exemption_tax_id`, `resolve_vies_exemption_tax_id_with_fallback`).

**Delete tax:** `DELETE /api/v1/taxes/{id}` — se la tax è referenziata restituisce **422** con `error_code: TAX_IN_USE` e `details: { orders, documents, is_reverse_charge }` (BE-ALIQ-02).

---

## Ultime modifiche (2026-06-05) — BE-ALIQ-05 (Tax.percentage DECIMAL)

- Colonna `taxes.percentage`: `Integer` → `DECIMAL(5,2)` (modello SQLAlchemy + migration Alembic `20260605_0001`).
- Schema API: `percentage` come `Decimal` con risposta JSON numerica (`25.5`, `22`, …).
- Seed UE: Finlandia **25.5%** (prima troncata a 25).
- Setup idempotente: `setup_taxes_percentage_decimal_column()` in `scripts/setup_initial.py`.
- Deploy DB: `alembic upgrade head` **oppure** `python scripts/setup_initial.py` su MySQL.
- **Troubleshooting:** se PUT/POST invia `25.5` ma la response restituisce `26`, la colonna DB è ancora `INTEGER`. Verifica con `python scripts/check_tax_percentage_column.py` e applica la migration.
- Test: `tests/unit/schemas/test_tax_percentage_decimal.py`, `tests/integration/api/v1/test_tax_percentage_decimal.py`.

---

## Ultime modifiche (2026-06-05) — BE-ALIQ-04 (id_country int|null)

- `coerce_optional_int()` + validator Pydantic su `TaxSchema` / `TaxResponseSchema` — accetta input stringa (`"5"`) e serializza sempre `int | null`.
- Serializzazione centralizzata: `serialize_tax_response()` / `serialize_taxes_response()` usate da router Tax e `InitService._get_taxes`.
- Endpoint Tax (`GET/POST/PUT`) e `/api/v1/init/?include=static` restituiscono `id_country` tipizzato in modo coerente (niente stringhe difensive lato FE).
- Test: `tests/unit/schemas/test_tax_id_country.py`, `tests/integration/api/v1/test_tax_id_country.py`.

---

## Ultime modifiche (2026-06-05) — BE-ALIQ-03 (cache init su write Tax/Settings)

- Helper condiviso `invalidate_init_data_cache()` in `src/core/cache.py` — invalida `init_data:static` e `init_data:full`.
- Chiamato su **tutti** i write: `POST/PUT/DELETE /api/v1/taxes/`, `PUT .../set-country-default`, `PUT /api/v1/settings/` (reverse charge).
- Nessuna invalidazione se delete tax fallisce con `TAX_IN_USE`.
- Test: `tests/unit/core/test_init_cache_invalidation.py`, estensioni in `test_tax_service.py` e `test_settings_reverse_charge.py`.

---

## Ultime modifiche (2026-06-05) — BE-ALIQ-02 (delete Tax strutturato)

- Pre-check utilizzo tax prima della delete: righe ordine, dettagli documenti fiscali, `reverse_charge_id_tax` in settings VIES.
- Errore **422** con `error_code: TAX_IN_USE` (non più 500 generico su FK).
- File: `src/repository/tax_usages.py`, `TaxRepository.find_usages`, `TaxService.delete_tax`.
- Test: `tests/unit/repository/test_tax_find_usages.py`, `tests/unit/services/test_tax_service.py` (classe `TestTaxServiceDelete`), `tests/integration/api/v1/test_tax_delete.py`.

---

- Sync PS: regole tax invariate; nessun import di resolver VIES in `prestashop_service`.
- Esenzione manuale allineata a `reverse_charge_id_tax` (`app_configurations` categoria `vies`).
- Creazione ordine con `vies_status=eligible`: `id_tax` VIES su righe/spedizione senza tax esplicita.
- Test: `tests/unit/vies/test_vies_exemption_tax.py`, `tests/unit/repository/test_order_create_vies_eligible_tax.py`.

---

## Ultime modifiche (2026-05-27) — fix `vies_status` PUT/GET MySQL

**Problema:** dopo `PUT /api/v1/orders/{id}` con `"vies_status": "eligible"`, il `GET` restituiva `null`.

**Causa:** SQLAlchemy mappava l'enum MySQL con i **nomi** (`ELIGIBLE`) mentre DB/sync usano i **valori** (`eligible`).

**Fix:** `Enum(ViesStatus, values_callable=...)` in `src/models/order.py`; `OrderRepository.update` consente reset esplicito a `null`.

**Verifica:** `pytest tests/integration/api/v1/test_order_put_vies_status.py` — riavviare `uvicorn` dopo il deploy.

---

## Ultime modifiche (2026-05-27) — BE-VIES-FALLBACK-GLOBAL

**Scope:** Fallback IVA globale + reverse charge VIES (prerequisito FE-VIES-3 STEP 3).

| Metodo | Path | Descrizione |
|--------|------|-------------|
| GET | `/api/v1/taxes/global-default` | Default IVA globale (`id_country` null) |
| PUT | `/api/v1/taxes/{id}/set-country-default` | Default paese **o** globale |
| GET/PUT | `/api/v1/settings/` | Facade: legge/scrive `reverse_charge_id_tax` su `app_configurations` (category `vies`) |
| GET | `/api/v1/app_configurations/by-category/vies` | Lista configurazioni VIES |

`POST/PUT /api/v1/taxes/` accettano `id_country: null`. `/api/v1/init/` include `settings.reverse_charge_id_tax`.

Persistenza: `app_configurations` — `category=vies`, `name=reverse_charge_id_tax`, `value=<id_tax>`. Nessuna tabella `settings` dedicata.

Migration: `alembic upgrade head` (revision `20260527_0003` migra da `settings` se presente).

## Ultime modifiche (2026-05-27) — BE-VIES-CLEANUP-SEED

**Scope:** Rimozione seed aliquote UE (BE-VIES-1) da prod/stage.

- Seed disattivato in `scripts/setup_initial.py` (attivo solo con `SEED_EU_VAT_TAXES=1` per test/CI).
- Logica seed/cleanup: `src/vies/eu_vat_seed.py`.
- Migration: `alembic upgrade head` → `20260527_0001_cleanup_be_vies_1_seed`.
- Guida: [docs/BE_VIES_CLEANUP_SEED.md](docs/BE_VIES_CLEANUP_SEED.md).

## Ultime modifiche (2026-05-27) — BE-VIES-2

**Scope:** Fase 2/4 VIES — sync PrestaShop + API gestionale.

- **Sync:** `vies_status_resolver` + bulk INSERT in `prestashop_service`; P.IVA da `vat_number` o `vat`.
- **Lista, dettaglio, creazione:** `vies_status` su `GET /api/v1/orders/`, `GET /api/v1/orders/{id}`, body/response `POST /api/v1/orders/`, body `PUT /api/v1/orders/{id}`.
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
