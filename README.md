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
- `FASTLDV_API_KEY` (per app magazzino FastLDV; vedi sotto)

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
| GET | `/api/v1/orders/{id}/pdf` | PDF stampa singolo ordine (layout elettronew: logo, barcode, intestazione/consegna, righe, totali) |

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

## Ultime modifiche (2026-06-22) — `taxes.electronic_code` + FatturaPA Natura (step 1)

**Contratto API Tax (allineato a FatturaPA):**

| Campo | Contenuto | Uso XML FatturaPA |
|-------|-----------|-------------------|
| `electronic_code` | Codice natura breve (es. `N3.1`, `N3.2`) | tag `<Natura>` |
| `note` | Descrizione normativa (es. `Non imponibili - esportazioni`) | tag `<RiferimentoNormativo>` |

Il FE invia codice e descrizione su campi separati; non concatenare `CODICE - DESCRIZIONE` in `electronic_code`.

**DB:** colonna `taxes.electronic_code` portata a `VARCHAR(255)` (migration `20260622_0001`; head applicata).

**FatturaPA (step 1):**

- Fix bug riga 527: rimosso `{tax_electronic_code:.2f}` (crash su stringhe).
- `_prepare_order_data_from_fiscal_document` passa `tax_electronic_code` e `tax_note` da `Tax`.
- Helper `src/services/external/fatturapa_natura.py` — normalizza codice per `<Natura>`.
- Validator: accetta sottocodici `N3.1`–`N6.9`, rifiuta stringhe estese.

**Prossimi step (non in questo commit):** Natura per riga ordine, ramo VIES `N3.2`, tax per `id_tax` riga.

**Handoff FE:** [docs/FE_HANDOFF_TAX_ELECTRONIC_CODE.md](docs/FE_HANDOFF_TAX_ELECTRONIC_CODE.md)

Test: `tests/unit/services/external/test_fatturapa_natura.py`, `tests/integration/api/v1/test_tax_electronic_code_length.py`.

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

## Integrazione FastLDV (magazzino)

API dedicate per l’app browser FastLDV (sostituisce `checkOrderData` + `validate.php` di Smarty con **una sola GET**). Autenticazione tramite header `X-FastLDV-Key` (no JWT).

| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET | `/api/v1/fastldv/order/{code}` | Dati ordine + righe + `validation` (`200` stampabile, `422` bloccato con payload completo) |
| POST | `/api/v1/fastldv/notify-print` | Aggiorna `shipping.tracking` dopo stampa etichetta |

**Identificatori:** `id_order` = PK interna incrementale; `id_origin` = ID PrestaShop o **`0`** se ordine nato in app (non viene sostituito con `id_order`). Per ordini PS i due numeri differiscono (es. `id_origin=457300`, `id_order=48564`). Barcode `{code}`: ID PS se sync, altrimenti `id_order`. Etichetta: `document.num_doc`. Angular/SSE: sempre `id_order`.

**Nota:** la **multispedizione** (`is_multishipping`, più spedizioni per ordine) è **accantonata in v1**: GET e notify-print usano solo la spedizione principale (`orders.id_shipping`).

Variabili `.env`:

- `FASTLDV_API_KEY` — chiave obbligatoria per gli endpoint sopra
- `FASTLDV_BYPASS_VALIDATE_IDS` — (opz.) lista `id_origin` separati da virgola che saltano la validazione

Esempio smoke test:

```bash
curl -H "X-FastLDV-Key: $FASTLDV_API_KEY" "http://localhost:8000/api/v1/fastldv/order/69099?carrier=BRT+NAPOLI"
```

Guida completa: [docs/BE_FASTLDV_INTEGRATION.md](docs/BE_FASTLDV_INTEGRATION.md). Traccia implementazione BE: [.cursor/tasks_claude/fastLdv/IMPLEMENTAZIONE_TECNICA_FASTLDV.md](.cursor/tasks_claude/fastLdv/IMPLEMENTAZIONE_TECNICA_FASTLDV.md). Handoff team app magazzino: [docs/PROMPT_FASTLDV_APP_CUTOVER.md](docs/PROMPT_FASTLDV_APP_CUTOVER.md).

**Real-time tracking (BE-FASTLDV-EVT):** dopo `notify-print` il BE emette `order.tracking.updated` (payload: `id_order`, `tracking`, `awb`); FE Angular consuma `GET /api/v1/events/stream`. Handoff: [docs/FE_HANDOFF_SSE_TRACKING.md](docs/FE_HANDOFF_SSE_TRACKING.md).

**Test:** `pytest tests/unit/services/test_fastldv_order_service.py tests/integration/api/v1/test_fastldv.py tests/integration/api/v1/test_events_sse.py -v`

## Ultime modifiche (2026-06-18) — Documentazione FastLDV

**Scope:** Traccia tecnica implementazione FastLDV in `.cursor/tasks_claude/fastLdv/IMPLEMENTAZIONE_TECNICA_FASTLDV.md` (architettura, flussi, mapping, test, stato task BE-FASTLDV-1/2/EVT).

## Ultime modifiche (2026-06-12) — Fix calcolo totali preventivi

**Scope:** Correzione errore 500 su `GET /api/v1/preventivi`.

- `calculate_order_totals` / `calculate_price_with_tax`: conversione sicura di aliquote IVA `Decimal` (colonna `Tax.percentage`) in `float` prima dei calcoli.
- `OrderDocumentService.calculate_totals`: mappa aliquote normalizzata a `float`.
- Test: `tests/unit/services/test_calculate_order_totals.py`.

## Ultime modifiche (2026-06-11) — BE-FASTLDV-EVT

**Scope:** Real-time tracking verso Angular dopo stampa FastLDV.

- `EventType.ORDER_TRACKING_UPDATED` (`order.tracking.updated`) + emit in `POST /fastldv/notify-print`
- `SseFanoutService` + `GET /api/v1/events/stream` (JWT, `text/event-stream`)
- Test: `tests/integration/api/v1/test_events_sse.py`, `tests/unit/events/test_sse_fanout_service.py`

## Ultime modifiche (2026-06-09) — BE-FASTLDV-1/2

**Scope:** Fase 1 backend integrazione FastLDV (ordine unificato + notify-print).

- Router `src/routers/fastldv.py`, service `FastLdvOrderService`, auth `X-FastLDV-Key`, settings `FASTLDV_API_KEY` / `FASTLDV_BYPASS_VALIDATE_IDS`.
- `OrderRepository.get_by_origin_id(id_origin, id_store?)` con filtro opzionale multi-negozio.
- Validazione allineata a `validate.php` (priorità bypass → annullato → bloccato → non pagato → già spedito → non pronto → OK/ristampa).
- Alias legacy Smarty in risposta (`data.legacy`) per transizione adapter PHP.
- Multispedizione esplicitamente fuori scope v1 (solo `orders.id_shipping`).
- Dual lookup FastLDV: `id_origin` PrestaShop oppure `id_order` per ordini gestionale (`id_origin=0`).

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

## API — Borderò spedizioni

| Metodo | Path | Descrizione |
|--------|------|-------------|
| POST | `/api/v1/bordero/generate` | PDF riepilogo spedizioni in stato **Spediti** (`id_order_state=3`) per `carriers_api.id_carrier_api`, con tracking valorizzato |

**Body:** `{ "carrier_id": int, "update_status": bool, "date_from"?: "YYYY-MM-DD", "date_to"?: "YYYY-MM-DD" }`

**Header risposta (PDF blob):**

| Header | Descrizione |
|--------|-------------|
| `X-Bordero-Order-Count` | Spedizioni incluse nel PDF |
| `X-Bordero-Order-Ids` | CSV `id_order` inclusi |
| `X-Bordero-Hint-Code` | Solo se count=0: `MISSING_TRACKING`, `NO_ORDERS_FOR_CARRIER`, `INACTIVE_CARRIER`, `GENERIC` |
| `X-Bordero-Hint-Message` | Messaggio operatore in italiano, URL-encoded (`decodeURIComponent` in FE) |
| `X-Bordero-Missing-Tracking-Count` | Ordini Spediti con corriere corretto ma senza AWB |

Permesso RBAC: `shipments.create`. Test: `tests/integration/api/v1/test_bordero.py`.

---

## API — DDT PDF

Prefisso `/api/v1/ddt`. Permesso RBAC: `ddt.read`.

| Metodo | Path | Descrizione |
|--------|------|-------------|
| GET | `/api/v1/ddt/pdf/{id_order_document}` | PDF Documento di Trasporto (`Content-Disposition: attachment`) |

Identificatore: PK gestionale `id_order_document` (non `id_order`).

Handoff FE: [docs/FE_HANDOFF_DDT_PRINT_PDF.md](docs/FE_HANDOFF_DDT_PRINT_PDF.md) — prompt chat: [.cursor/tasks_claude/prompt_FE_ddt_print_pdf.md](.cursor/tasks_claude/prompt_FE_ddt_print_pdf.md).

---

## Ultime modifiche (2026-06-18) — Backlog FatturaPA implementazione

Creato backlog operativo dei task ancora da sviluppare per FatturaPA (gap analysis rispetto al codice esistente):

- [`.cursor/tasks_claude/fatturapa_backlog_implementazione.md`](.cursor/tasks_claude/fatturapa_backlog_implementazione.md) — task P0–P3, ordine di implementazione, checklist go-live
- Piano tecnico di riferimento: [`.cursor/tasks_claude/fatturapa_riassunto_piano.md`](.cursor/tasks_claude/fatturapa_riassunto_piano.md)

---

## Ultime modifiche (2026-06-18) — Riconciliazione backlog BE

Backlog unificato allineato allo stato del codice: [`.cursor/tasks_claude/BACKLOG_UNIFICATO.md`](.cursor/tasks_claude/BACKLOG_UNIFICATO.md).

**Chiusi:** BE-FASTLDV-1/2, BE-FASTLDV-EVT (implementazione), BE-ALIQ-02..05, BE-TAX-DECIMAL, BE-RETURN-PRICE-FIX.

**Ancora aperti (BE):** REPLAN-AS400-PR7, BE-FASTLDV-3 (opz.), BE-FASTLDV-EVT (QA), BE-ALIQ-06/07/08, BE-1, BE-TAX-DEFINE-FIX, BE-VIES-4, BE-INFRA-ALEMBIC, T1.

---

## Ultime modifiche (2026-06-16) — Fix calcolo righe reso (doppia IVA)

- **Problema:** in creazione/aggiornamento reso, se il FE inviava `unit_price` con l'importo **con IVA** dell'ordine (es. 289,97 €), il backend lo trattava come imponibile e ricalcolava l'IVA (totale errato, es. 363,91 € invece di 289,97 €).
- **Fix:** helper `resolve_return_unit_prices` in `src/services/core/tool.py` — se `unit_price` coincide con `order_detail.unit_price_with_tax`, usa `unit_price_net` dell'ordine originale. Applicato in `FiscalDocumentService.create_return`, `FiscalDocumentRepository.create_return`, `calculate_return_totals` e `update_fiscal_document_detail`.
- Test: `tests/unit/services/core/test_resolve_return_unit_prices.py`.

---

## Ultime modifiche (2026-06-16) — Fix PDF DDT (Fase 1 + 2)

- **Fase 1 — Fix 500:** conversione esplicita `Decimal` → `float` in `DDTPDFService` e serializzazione spedizione in `DDTService.get_ddt_complete` (allineato al preventivo). Router con `try/except` 404/500.
- **Fase 2 — Correttezza layout:** IVA righe risolta via `TaxRepository.get_percentage_by_id` (non più `id_tax` come percentuale). Totali riga con sconto `%` / importo. Colli da `packages` (fallback `1`). Riepilogo IVA con aliquota dominante dalle righe.
- Test: `tests/unit/services/pdf/test_ddt_pdf_service.py`.

---

## Ultime modifiche (2026-06-15) — Stampa PDF singolo ordine

- Nuovo endpoint `GET /api/v1/orders/{id}/pdf` con layout allineato al documento ordine elettronew (logo + anagrafica, barcode Code39, blocchi Intestazione / Indirizzo di consegna, tabella righe con Impon./IVA/Sconto, riepilogo totali a destra).
- Servizio: `src/services/pdf/order_pdf_service.py`; orchestrazione in `OrderService.generate_order_pdf`.
- Permesso RBAC: `orders.read`. Risposta: PDF inline (`Content-Disposition: inline`).
- **Fix righe ordine (2026-06-15):** query PDF include `id_order_document IS NULL OR = 0` (sync PrestaShop salva `0`, non NULL).
- **Layout tabella righe:** colonne ribilanciate (Codice 40 mm, troncatura per larghezza con `get_string_width`, descrizione su max 2 righe).
- Handoff FE: [docs/FE_HANDOFF_ORDER_PRINT_PDF.md](docs/FE_HANDOFF_ORDER_PRINT_PDF.md) — prompt chat: [.cursor/tasks_claude/prompt_FE_order_print_pdf.md](.cursor/tasks_claude/prompt_FE_order_print_pdf.md).

---

## Ultime modifiche (2026-06-15) — Borderò hint diagnostici (count=0)

- Quando `X-Bordero-Order-Count=0`, la risposta include header `X-Bordero-Hint-*` con la causa reale (es. ordini Spediti **senza tracking** vs assenza ordini per corriere).
- Il FE può mostrare `X-Bordero-Hint-Message` invece del messaggio generico "nessun ordine per questo corriere".
- File: `OrderRepository.get_bordero_zero_hints`, `BorderoService`, `src/routers/bordero.py`.

---

## Documentazione

- [DOCUMENTAZIONE.md](DOCUMENTAZIONE.md) – panoramica e architettura  
- [QUICK_START.md](QUICK_START.md) – avvio rapido e comandi  
- [docs/](docs/) – guide specifiche (eventi, plugin, sync, ecc.)
- [.cursor/tasks_claude/BACKLOG_UNIFICATO.md](.cursor/tasks_claude/BACKLOG_UNIFICATO.md) – backlog unificato FE+BE (fonte di verità task; riconciliato 2026-06-18)
- [.cursor/tasks_claude/fatturapa_backlog_implementazione.md](.cursor/tasks_claude/fatturapa_backlog_implementazione.md) – task FatturaPA da implementare (P0–P3, go-live)
- [.cursor/tasks_claude/fatturapa_riassunto_piano.md](.cursor/tasks_claude/fatturapa_riassunto_piano.md) – riassunto normativa FatturaPA e piano fasi
- [docs/BE_FASTLDV_INTEGRATION.md](docs/BE_FASTLDV_INTEGRATION.md) – integrazione app magazzino FastLDV
