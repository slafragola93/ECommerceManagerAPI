# Backlog Elettronew — Gestionale e-commerce

> Backlog generato dalla sessione di consolidamento RBAC + refactor FE del 2026-05-12/13.
> Tutti i task sono organizzati per priorità, area (BE/FE), stato e dettaglio implementativo.

---

## 📊 Sommario stato

| Area | Done | In corso | Backlog | Epic |
|---|---|---|---|---|
| Backend | 26 (…, BE-VIES-CLEANUP-SEED, BE-VIES-FALLBACK-GLOBAL) | 0 | 4 + epic aliquote (vedi `PROGRAMMA_BE_aliquote_vies.md`: BE-ALIQ-01…08) | 0 |
| Frontend | 6 (FE-3, FE-7, FE-9, FE-11, FE-AUTOTAB ⚠️ deprecato, FE-MULTISHIP-BADGE) | 0 | 13 (FE-1, FE-4, FE-5, FE-6, FE-8, FE-10, FE-12, FE-13, T1, FE-REFACT, REPLAN-SHIPMENT-WORKFLOW, FE-BORDERO, FE-ORDER-CANCEL) | 2 (N1, N2) |

---

## ✅ Task completati (storico)

### BE-DDT-PRINT-PDF — Fix PDF DDT Fase 1–2 (chiuso 2026-06-16)

**Scope:** Endpoint `GET /api/v1/ddt/pdf/{id_order_document}` — fix 500 (`Decimal` vs `float`), IVA righe via `TaxRepository`, sconti, colli da `packages`, error handling router.

**File:** `ddt_pdf_service.py`, `ddt_service.py`, `ddt.py`, `tests/unit/services/pdf/test_ddt_pdf_service.py`

**Handoff FE:** `docs/FE_HANDOFF_DDT_PRINT_PDF.md` · task aperto **FE-DDT-PRINT-PDF** in `BACKLOG_UNIFICATO.md`

---

### BE-VIES-FALLBACK-GLOBAL — Tax globali fallback + reverse_charge (chiuso 2026-05-27)

**Scope:** Default IVA globale (`id_country IS NULL`) + setting VIES reverse charge.

**Tax CRUD:**
- `POST/PUT /api/v1/taxes/` accettano `id_country: null`
- `PUT /api/v1/taxes/{id}/set-country-default` funziona per default paese **e** globale
- `GET /api/v1/taxes/global-default` — default fallback globale
- `set_global_default_atomic` — un solo `is_default=1` con `id_country IS NULL`
- `get_tax_info_by_country` — fallback: default paese → globale → app_config

**Settings (refactor su app_configurations):**
- `reverse_charge_id_tax` in `app_configurations` (`category=vies`, `name=reverse_charge_id_tax`, `value` = id_tax)
- `GET/PUT /api/v1/settings/` — facade compatibile FE
- `/api/v1/init/` static: `settings.reverse_charge_id_tax`
- Helper: `src/vies/vies_app_configuration.py`

**Risoluzione documento:** `src/vies/tax_resolution.py` → `resolve_tax_id_for_delivery()`

**Migration:** `20260527_0002` (storico settings), `20260527_0003` (migra → app_configurations, drop `settings`)

**Test:** `test_tax_global_default.py`, `test_settings_reverse_charge.py`, `test_tax_resolution.py`

### BE-VIES-CLEANUP-SEED — Rimozione seed BE-VIES-1 da DB (chiuso 2026-05-27)

**Scope:** Rimuovere aliquote UE pre-popolate dal seed BE-VIES-1 in prod/stage; seed solo test/CI.

**Seed runner originale (disattivato):**
- `src/vies/eu_vat_seed.py` → `setup_eu_country_taxes()` (logica estratta da `setup_initial`)
- `scripts/setup_initial.py` → invoca seed **solo** se `SEED_EU_VAT_TAXES=1`

**Migration cleanup:**
- `alembic/versions/20260527_0001_cleanup_be_vies_1_seed.py` — `DELETE` su `taxes` con `note LIKE '%BE-VIES-1 seed%'`, skip FK (`order_details`, `fiscal_document_details`, `shippings`)
- `downgrade`: ripristino idempotente via `setup_eu_country_taxes()`

**Doc:** `docs/BE_VIES_CLEANUP_SEED.md` (rollback, SQL diagnostica)

**Test:** `tests/unit/vies/test_be_vies_1_seed_cleanup.py`

**FE:** nessuna modifica; tab "Default per paese" vuota finché l'utente crea aliquote.

### BE-VIES-2 — VIES Fase 2: sync + filtro lista + esenzione manuale (chiuso 2026-05-27)

**Scope:** Backend — Fase 2/4 VIES (sync PrestaShop, API gestionale, eventi).

**Sync PrestaShop — file creati/modificati:**
- `src/services/vies/vies_status_resolver.py` + `__init__.py`
- `src/services/ecommerce/prestashop_service.py` — calcolo `vies_status` + bulk INSERT; fix `Address.vat` da `vat_number`/`vat`
- `tests/unit/services/vies/test_vies_status_resolver.py`
- `docs/ECOMMERCE_SYNC.md`

**Regole sync:** snapshot al sync; totali ordine restano quelli PrestaShop; nessuna chiamata VIES runtime.

**Campi PS esito VIES:** `vies_valid`, `vat_number_valid`, `valid_vat`, `vies`, `vies_checked`, `vies_status`.

**Filtro lista ordini:**
- `GET /api/v1/orders/?vies_status=eligible|not_eligible|null` (assenza param = tutti; `orders.read`)
- `OrderRepository._apply_vies_status_filter` in `get_all` / `get_count`
- Router: `_normalize_vies_status_filter` (422 su valore non valido)

**Esenzione VIES manuale (gestionale):**
- `PATCH /api/v1/orders/{id}/apply-vies-exemption` (`orders.update`)
- `POST /api/v1/orders/bulk-apply-vies-exemption` body `{ "order_ids": [...] }` — transazione atomica (`orders.update`)
- `OrderService.apply_vies_exemption` / `bulk_apply_vies_exemption`
- Ricalcolo righe: `_recalculate_order_lines_for_zero_tax` → `calculate_price_without_tax` (`src/services/core/tool.py`, stesso pattern di `order_detail_service._calculate_price_fields`)
- Ricalcolo totali ordine: `OrderService.recalculate_totals_for_order(order_id, commit=False)` in bulk/singolo core
- Imposta `order.vies_status = eligible`; crea/usa `Tax` al 0% se assente (`_get_zero_tax_id`)
- Evento: `ORDER_VIES_EXEMPTION_APPLIED` (`src/events/core/event.py`) payload `{order_id, previous_vies_status, applied_by_user_id, timestamp}`

**Test:** `test_order_repository_vies_filter.py`, `test_order_vies_exemption.py` (unit + integration).

### BE-VIES-1 — Fondamenta dati VIES + default IVA per paese (chiuso 2026-05-27)

**Scope:** Backend — Fase 1/4 del task VIES.

**Strategia:** Riuso di `Tax(id_country, is_default)` esistente. NIENTE nuova tabella `country_tax_rates` (audit ha rivelato sovrapposizione concettuale).

**File modificati:**
- `src/models/order.py` — aggiunto enum `ViesStatus` + colonna `vies_status` (nullable, indicizzata)
- `src/schemas/order_schema.py` — esposto `vies_status` in `OrderResponseSchema`, `OrderSimpleResponseSchema`, `OrderUpdateSchema`
- `src/repository/order_repository.py` — serializzazione `vies_status` in risposta ordine
- `src/repository/tax_repository.py` + interface — `get_default_by_country`, `get_default_by_country_iso`, `list_country_defaults`, `set_country_default_atomic`
- `src/services/routers/tax_service.py` + interface — `get_default_by_country*`, `set_country_default` (atomico, single-default invariant)
- `src/routers/tax.py` — 3 endpoint country-defaults
- `src/schemas/tax_schema.py` — `TaxCountryDefaultResponseSchema`, `model_config` su response
- `src/events/core/event.py` — `TAX_COUNTRY_DEFAULT_CHANGED`
- `scripts/setup_initial.py` — colonna `vies_status` su `orders` + seed 27 paesi UE (idempotente)

**Endpoint nuovi:**
- `GET /api/v1/taxes/country-defaults` (settings.read)
- `GET /api/v1/taxes/country-defaults/{iso_code}` (settings.read)
- `PUT /api/v1/taxes/{id_tax}/set-country-default` (settings.update)

**Seed:** 27 paesi UE con aliquote standard. NOTA: Finlandia seedata a 25% invece di 25.5% per limitazione `Tax.percentage` Integer — vedi BE-TAX-DECIMAL.

**Eventi:** `TAX_COUNTRY_DEFAULT_CHANGED` su `set_country_default`.

**Cache:** `init_data:static` e `init_data:full` invalidate su modifica default paese.

**Decisioni emerse da audit:**
- Riuso `Tax.id_country + is_default` invece di nuova `country_tax_rates`
- Convenzione progetto: `setup_initial.py` invece di Alembic (Alembic non in uso reale)
- RBAC action `read` non `view` (coerente con country.py/lang.py)

**Out-of-scope (a backlog separato):**
- Popolamento `vies_status` durante sync PrestaShop → Fase 2 (BE-VIES-2)
- FatturaPA N3.2 / art. 41 → Fase 4 (BE-VIES-4)
- `define_tax` rotto (non bloccante Fase 2) → BE-TAX-DEFINE-FIX
- Aliquote IVA decimali → BE-TAX-DECIMAL
- Migrazione a Alembic vero → BE-INFRA-ALEMBIC

### M1-M19 — Migrazione RBAC Backend (chiuso 2026-05-08)

**Commit:** `638ffbc` su `origin/master`
**Backup:** `backup/pre-rbac-merge-2026-05-08`
**Diff:** 52 file, 2928 insertions, 758 deletions
**Scope:** Migrazione completa dal vecchio `@authorize` al nuovo `require_permission` (RBAC granulare CRUD per modulo).
**File coperti:** 29 router, 197 endpoint, 17 moduli BE
**Helper aggiunti:** `require_permission(module, action)`, `check_permission(...)`, `_raise_permission_denied(module, action, reason)` con body strutturato

### FE-7 — ErrorInterceptor e wrapper backend errori (chiuso 2026-05-12)

**File modificati:**
- `src/app/core/helpers/error.interceptor.ts` — propaga HttpErrorResponse originale (no più `new Error()`)
- `src/services/routers/auth_service.py` — helper `_raise_permission_denied` con body strutturato `{error_code, message, details, status_code, reason}`
- `src/main.py` — `http_exception_handler` distingue `isinstance(exc.detail, dict)` per "spalmare" i campi nel wrapper standard
- `src/app/core/services/alert.service.ts` — branch wrapper backend con `getTitleForErrorCode()` per PERMISSION_DENIED/VALIDATION_ERROR/NOT_FOUND/BUSINESS_RULE_VIOLATION/HTTP_ERROR + parse difensivo JSON.parse per responseType:'text'

**Risultato:** errori 403/422 mostrano Swal contestuali invece di "Errore di connessione al server" generico.

### FE-3 — Direttiva `*hasPermission` wizard settings (chiuso 2026-05-12/13)

**File modificati:** 9 template HTML + 1 modulo
- `src/app/settings/settings.module.ts` — aggiunto `HasPermissionDirective` agli imports (standalone)
- `company-info.component.html`, `electronic-invoice.component.html`, `payment-methods.component.html`, `preferences.component.html`, `email-settings.component.html`, `ddt-sender.component.html`, `cash-register.component.html` (3 bottoni), `fatturapa.component.html`, `exempt-rates.component.html` — bottoni Salva con `*hasPermission="'settings'; action: 'update'"`
- `api-credentials.component.html` — SKIP (read-only)
- `src/app/tax/tax.component.ts` — rimosso subscribe-to-error che mostrava alert duplicato

**Esempio pattern:**
```html
<button *hasPermission="'settings'; action: 'update'" mat-flat-button color="primary" (click)="submit()">
  Salva
</button>
```

**Risultato:** `test_manager` non vede bottoni Salva su pagine senza `settings.update`, evita 403 a monte.

**Decisione di prodotto:** estensione del pattern alle altre pagine CRUD (orders, customers, quotes, ddt, ecc.) → debito tecnico bassa priorità. Le azioni sono già protette lato BE.

### FE-9 — Refactor handleError centralizzato (chiuso 2026-05-13)

**File creati:**
- `src/app/core/helpers/extract-error-message.ts` — helper centralizzato che gestisce wrapper backend, body stringa JSON (parse difensivo), FastAPI detail array/string, reason custom, Error JS, stringhe semplici

**File modificati (semplificato `handleError`):**
- `src/app/core/services/appConfigService.service.ts`
- `src/app/core/services/ddt.service.ts`
- `src/app/core/services/fiscal-documents.service.ts`
- `src/app/core/services/messages.service.ts`
- `src/app/core/services/quotes.service.ts`

**Pattern applicato:** rimossa costruzione manuale di errorMessage, mantenuto console.error per debug, propagato `throwError(() => error)` invece di `new Error()`.

**Effect aggiornati (usano `extractErrorMessage`):**
- `audit.effects.ts`, `ddt.effects.ts`, `notes.effects.ts`, `order-package.effects.ts`, `quotes.effects.ts`, `returns.effects.ts`, `shipping.effects.ts`, `user.effects.ts`, `customer.effects.ts` (in Ecommerce)

**Risultato:** eliminata trasformazione `HttpErrorResponse → Error JS` che impediva la lettura di `error.error.message` (wrapper backend) dagli effect downstream.

### FE-11 — Meta-reducer reset globale al logout (chiuso 2026-05-13)

**File creati:**
- `src/app/store/meta-reducers/clear-state-on-logout.ts` — meta-reducer NgRx che resetta tutti gli slice eccetto `layout` al dispatch di `[Authentication] Logout`

**File modificati:**
- `src/app/app.module.ts` — registrato `clearStateOnLogout` in `StoreModule.forRoot(rootReducer, { metaReducers })`

**Whitelist preservata:** `['layout']` (solo preferenze UI: tema, sidebar collapsed, layout type)

**Risultato:** al logout, tutti gli slice tornano a initialState. Niente data leak tra utenti consecutivi nella stessa sessione browser.

### FE-AUTOTAB — Auto-switch tab "Spedizione Confermata" dopo bulk LDV (chiuso 2026-05-14, ❌ DEPRECATO 2026-05-15)

**⚠️ DEPRECATO:** Il nuovo flusso ordini (vedi REPLAN_SHIPMENT_WORKFLOW.md v2) non prevede più lo spostamento automatico a "Spedizione Confermata" dopo bulk LDV. PR 6 del piano replan **rimuove** questa logica. Conservato come storico del lavoro fatto.

**Tipo:** UX miglioramento
**Scope:** Frontend
**Priorità:** Bassa
**Stima:** ~30 min (effettivi)

**File modificati:**
- `src/app/pages/orders/order-list/order-list.component.ts` — aggiunta logica auto-switch nel subscribe a `ShipmentsActions.bulkCreateShipmentsSuccess`

**Comportamento:**
- Dopo bulk-create LDV andata completamente a buon fine (`response.failed.length === 0`), la tab della lista ordini viene spostata automaticamente a "Spedizione Confermata"
- Se ci sono ordini falliti (parziale), la tab NON cambia → utente gestisce errori sulla tab di partenza
- Riusa `spedizioneConfermataState` già calcolato nello stesso subscribe (no duplicazione lookup)
- Riusa il metodo centralizzato `switchToStateTab(stateId)` che gestisce reset paginazione e filtri

**Risultato:** flusso operatore più fluido. Dopo conferma spedizioni, vede subito gli ordini appena spediti senza dover cambiare tab manualmente.

**Note tecniche:**
- Si applica SOLO al caso bulk. La singola spedizione (`createShipmentSuccess`) ha già il suo handler che cambia tab con assegnazione diretta a `selectedStateId` — pattern incoerente che potrebbe essere uniformato a `switchToStateTab` in futuro (debito tecnico minore).
- Bug pre-esistente non toccato: doppia `includes('spedizione confermata')` nella `find()` (clone copia-incolla, innocuo).

### FE-MULTISHIP-BADGE — Tracciabilità ordini multispedizione nella lista (chiuso 2026-05-14, ❌ DEPRECATO 2026-05-15)

**⚠️ DEPRECATO:** Il nuovo flusso ordini (vedi REPLAN_SHIPMENT_WORKFLOW.md v2) rimuove la multispedizione dal FE. PR 2 e PR 3 del piano replan **rimuovono** badge + filtro multispedizione + utility `multishipping-status.util.ts`. Conservato come storico del lavoro fatto.

**Tipo:** UX miglioramento — distinzione visuale + filtro client-side
**Scope:** Frontend
**Priorità:** Media (problema operativo emerso dopo FE-AUTOTAB)
**Stima:** ~1h (effettivi)

**Problema risolto:**
Dopo FE-AUTOTAB, gli ordini multispedizione con LDV generate venivano spostati in tab "Spedizione Confermata", ma diventavano visivamente indistinguibili dagli ordini con spedizione singola completata. L'operatore non riusciva a capire se l'ordine aveva altre LDV ancora da generare.

**Nuovi file:**
- `src/app/pages/orders/utils/multishipping-status.util.ts` — utility pura riusabile che espone:
  - `MultishippingState = 'none' | 'partial' | 'complete' | 'unknown'`
  - `MultishippingProgress` (isMulti, state, shipmentsCount, orderedQty, shippedQty, isPartial, isComplete)
  - `getMultishippingProgress(order: OrderVM)` — confronta `order.products[].quantity` (ordinato) vs somma `multishippings[].items[].quantity` (spedito). Ritorna `unknown` quando `is_multishipping=true` ma `multishippings` non è caricato.

**File modificati:**
- `src/app/pages/orders/models/order.vm.ts` — esteso `OrderFilters` con `multishippingOnly?: boolean` (filtro client-side, coerente con `fiscal_invoice_emitted` / `fiscal_billing_error`)
- `src/app/pages/orders/components/order-state-tabs/order-state-tabs.component.{ts,html,scss}`:
  - Nuovo `@Input multishippingOnly` + `@Output multishippingFilterChange`
  - Nuovo getter `isSpedizioneConfermataTab` (match name-based, case-insensitive)
  - Nuovo gruppo "Spedizione" nella fiscal-filters-row con checkbox "Multispedizione", visibile solo su tab "Spedizione Confermata"
  - Nuovo divider + label "Spedizione" + stile dedicato `fiscal-filters-label--shipping` (color primary)
- `src/app/pages/orders/order-list/order-list.component.{ts,html}`:
  - Wiring `[multishippingOnly]` / `(multishippingFilterChange)` verso `OrderStateTabsComponent`
  - Nuovo handler `onMultishippingFilterChange(checked)`
  - `applyFilters()` estesa con filtro `getMultishippingProgress(order).isMulti`
  - `onFiltersChange()` preserva `multishippingOnly` quando arrivano filtri da `OrderFiltersComponent` (stesso pattern dei filtri fiscali)
  - `onOrderStateFilterChange()` resetta automaticamente `multishippingOnly` quando si esce dalla tab "Spedizione Confermata" (evita filtri invisibili attivi)
  - Nuovo helper privato `isSpedizioneConfermataState(stateId)`
- `src/app/pages/orders/components/order-status-cell/order-status-cell.component.{ts,html,scss}`:
  - Helper esposti al template: `getMultishippingProgress()`, `multishippingBadgeClass()`, `multishippingIconClass()`, `multishippingLabel()`, `multishippingTitle()`
  - Nuovo blocco `<div class="multishipping-status-row">` con badge dedicato, posizionato sotto il semaforo fatturazione
  - Rimossa la vecchia icona singola `ri-truck-line text-primary` dalla `status-icons-row` (informazione ora ridondante)
  - Stile badge volutamente diverso dal `fiscal-status-badge` (solid fill + testo bianco + ombra leggera):
    - Completa: `#0d9488` (teal) — "Multi 3/3 OK"
    - Parziale: `#ea7a17` (arancio) — "Multi 1/3"
    - Unknown: `#475569` (slate) — "Multispedizione" (tooltip spiega)

**Comportamento finale UX:**
| Scenario | Cosa vede l'utente |
|---|---|
| Ordine non multispedizione | Nessun badge (invariato) |
| Multispedizione completa | Badge teal pieno: "Multi 3/3 OK" |
| Multispedizione parziale | Badge arancio pieno: "Multi 1/3" |
| Multispedizione con `multishippings` non caricato | Badge slate pieno: "Multispedizione" |
| Tab "Spedizione Confermata" | Checkbox "Multispedizione" disponibile in barra |
| Altre tab | Checkbox nascosta; se era attiva, viene resettata automaticamente |
| Filtro attivo | Mostra tutti gli ordini multispedizione (parziali, completi e unknown) |

**Vincoli architetturali rispettati:**
- Nessun HTTP nei component
- Nessun nuovo slice NgRx
- Nessuna duplicazione di componenti shared
- Logica di dominio (`getMultishippingProgress`) isolata in utility riusabile
- Filtro coerente con il pattern esistente dei filtri client-side fiscali
- Component presentazionali rimangono "stupidi": solo `@Input` / `@Output`

**Verifica:** `npm run build` exit 0; 0 nuovi lint introdotti; 3 warning pre-esistenti rimasti (non legati: `@HostListener` signature in tabs, 2× NG8107 su `order.shipping?.packages` in status-cell, `OrderCarrierCellComponent` import non usato in order-list).

### BE-AUTOSTATE — Rimozione auto-update stato ordine post-creazione spedizione (chiuso 2026-05-21)

**Tipo:** Bug fix architetturale + diagnostica
**Scope:** Backend
**Priorità:** Alta
**Stima:** ~2h (effettivi, inclusi audit completo + diagnostica + script verifica)

**Contesto:**
Nel nuovo workflow ordini (REPLAN_SHIPMENT_WORKFLOW v2) lo stato ordine deve essere gestito SOLO manualmente dall'operatore. La creazione spedizione (singola o bulk) NON deve più cambiare automaticamente lo stato a "Spedizione Confermata" (4) o "Multispedizione" (7). Inoltre lo stato 7 non è più gestito dal FE, nessun ordine deve più essere reindirizzato lì.

Sintomo riportato: dopo creazione spedizione o cambio manuale di stato, al refresh della lista lo stato dell'ordine torna automaticamente a 4 (sez. 11 del replan).

**File modificati:**
- `src/routers/shipments.py` — rimosso step 6 in `create_shipment` (singolo) che faceva `update_order_status(order_id, 4)` o `update_order_status(order_id, 7)` dopo l'emit di `SHIPMENT_CREATED`. Stesso blocco rimosso anche dentro il loop di `bulk_create_shipments`. Sostituiti con commento marker `REPLAN-SHIPMENT-WORKFLOW`. Mantenuto intatto: `emit_event(SHIPMENT_CREATED)`, `successful.append()` / `failed.append()` / `continue`, gestione AWB e tracking documento.
- `src/main.py` — agganciato setup diagnostico opt-in nel lifespan + middleware HTTP che popola `ContextVar` con URL/metodo richiesta corrente. Zero overhead se env var non attiva.

**Nuovi file:**
- `src/core/diagnostics/__init__.py`
- `src/core/diagnostics/order_state_audit.py` — listener SQLAlchemy `before_update` su `Order`. Per ogni write su `id_order_state` logga `id_order`, `old → new`, URL+metodo richiesta, stack trace dei frame del progetto. Output su `logs/order_state_audit.log`. Attivabile via `ORDER_STATE_AUDIT=1`.
- `scripts/verify_order_state.ps1` — script PowerShell che bypassa il FE: login, bulk-status, attesa 60s senza FE attivo, rilettura. Dimostra in modo isolato che il BE non ribalta lo stato.
- `.cursor/tasks_claude/PR6_FE_PATCH_INSTRUCTIONS.md` — istruzioni operative per PR 6 lato FE su `webmarke26`.

**Audit BE completo (sospettati esclusi):**
- `OrderService.update_order_status` — applica solo lo stato richiesto, niente override
- `OrderRepository.update` — usa `model_dump(exclude_unset=True)`, non tocca campi non in payload
- Plugin `platform_state_sync` — outbound only, scrive `id_ecommerce_state` (NON `id_order_state`)
- Plugin `as400_validate_order_megawatt` — `enabled: false` in yaml, e comunque match solo `1→2`
- Plugin `email_notification` — `enabled: false`, solo log
- Background `tracking_polling_service` → `sync_shipping_states_from_tracking_results` — aggiorna solo `Shipping.id_shipping_state`
- Background `order_state_sync_service` (1h) — aggiorna solo `ecommerce_order_states` (mapping piattaforma)
- Inbound PrestaShop sync — inserisce nuovi ordini con state=1, non aggiorna esistenti
- Tabella `platform_state_triggers` — regole outbound (locale → piattaforma)
- `cached_order_repository` — definito ma non risolto in DI dei router (non in uso)
- Endpoint GET `/orders/` e `/orders/{id}` — leggono `order.id_order_state` direttamente (no computed)
- Nessun listener SQLAlchemy custom su `Order`, nessun trigger DB nelle migration

**Diagnosi finale del sintomo:**
Doppia causa. Una BE (sorgente diretta, ora rimossa con questa PR), una FE (sorgente indiretta tramite auto-dispatch NgRx, da fare con PR 6). Prove timeline log uvicorn `terminals/5.txt` per ordine 69083 il 2026-05-21:
- 12:14:24 POST `/orders/bulk-status` `[id_order_state: 3]` ← clic operatore manuale
- 12:14:48 GET `/orders/...` ← refresh lista
- 12:14:50 POST `/orders/bulk-status` `[id_order_state: 4]` ← AUTO-DISPATCH FE (gap 2.2s, tempo insufficiente per click umano)

**Verifica:**
- `grep "update_order_status.*4\|update_order_status.*7" src/routers/shipments.py` → 0 occorrenze
- `grep "REPLAN-SHIPMENT-WORKFLOW" src/routers/shipments.py` → 2 marker (single + bulk)
- `grep "SHIPMENT_CREATED" src/routers/shipments.py` → emit_event presente in entrambi gli endpoint
- ReadLints: nessun errore introdotto

**Residuo BE non urgente:**
`src/services/routers/shipping_service.py:597` ha ancora `update_order_status(request.id_order, 7)` in `create_multi_shipment`. Non è la causa attuale (multispedizione rimossa dal FE → endpoint non più invocato), ma è coerente con il replan rimuoverlo come follow-up.

**Cosa NON risolve questa PR:**
Il sintomo del "ribalto stato" continuerà finché PR 6 lato FE non viene applicata su `webmarke26` (rimuovere auto-dispatch `OrdersActions.bulkUpdateStatus → 4` da `bulkCreateShipmentsSuccess` e `createShipmentSuccess` in `order-list.component.ts`). Le istruzioni dettagliate sono in `.cursor/tasks_claude/PR6_FE_PATCH_INSTRUCTIONS.md`.

### BE-ORDERS-SORT — Ordinamento configurabile su `GET /api/v1/orders/` (chiuso 2026-05-22)

**Tipo:** Feature backend (puramente applicativa, no migration DB)
**Scope:** Backend
**Priorità:** Media (sblocca correttezza FE su tab "newest first")
**Stima:** ~1h

**Contesto:**
L'endpoint `GET /api/v1/orders/` esponeva paginazione e molti filtri ma nessun parametro di ordinamento. Il repo applicava implicitamente `ORDER BY id_order ASC` (dal più vecchio al più recente) e qualsiasi tentativo del client di esprimere un ordine veniva ignorato.

Sul FE (Angular, modulo `pages/orders`) la lista è organizzata per tab di stato ordine: ciascun tab fa una **singola chiamata** `GET /orders/?order_states_ids=X&date_from=...&date_to=...&limit=N`. Con `limit` < totale ordini del tab nella finestra, il BE restituiva sistematicamente i più vecchi e tagliava fuori i più recenti → gli ordini appena creati (`id_order` alto, tipicamente in stato "In Preparazione") non arrivavano mai al client, mentre quelli in "Spediti"/"Spedizione Confermata" — più vecchi — erano pienamente visibili.

Questa PR risolve il problema esponendo l'ordinamento al client. Default cambiato a `id_order DESC` per allinearsi al bisogno UX più comune ("newest first") senza richiedere modifiche al FE per le chiamate già esistenti — anche se in pratica il FE passerà i nuovi param esplicitamente per chiarezza (vedi sezione "Coordinamento FE").

**File modificati:**
- `src/repository/order_repository.py`:
  - Nuove costanti di classe `ALLOWED_ORDER_BY_FIELDS = {"id_order": Order.id_order, "date_add": Order.date_add}` e `ALLOWED_ORDER_DIRECTIONS = {"asc", "desc"}` per whitelistare in modo dichiarativo i campi ordinabili. Nessun ORDER BY dinamico da stringa libera (no SQL injection).
  - `get_all(...)` esteso con `order_by: str = "id_order"` e `order_direction: str = "desc"`. Validazione difensiva (fallback a default in caso di valori fuori whitelist, anche se il router già valida via `Literal`).
  - ORDER BY clausola riscritta come `[primary_sort, asc(Order.id_order)]` — il tie-breaker `id_order ASC` viene sempre applicato come secondo criterio per garantire paginazione deterministica anche quando `order_by` è una data e i timestamp coincidono. Aggiunto `from sqlalchemy import asc`.
- `src/repository/interfaces/order_repository_interface.py` — aggiornata la signature di `get_all` con i due nuovi parametri keyword (default `id_order` / `desc`).
- `src/routers/order.py`:
  - Nuovi query parameter su `GET /api/v1/orders/`:
    - `order_by: Literal["id_order", "date_add"] = "id_order"` (FastAPI restituisce 422 automaticamente per valori fuori whitelist).
    - `order_direction: str = "desc"` (validazione manuale case-insensitive: normalizzato a lowercase e validato contro `{"asc","desc"}`, restituisce 422 in caso di mismatch per coerenza con la validazione FastAPI degli altri param).
  - Default `desc` su `id_order`: **cambia il comportamento storico osservabile** (il repo applicava implicitamente `ASC`). Il nuovo default è quello "naturale" per una lista ordini.
  - Docstring + description OpenAPI estesi con descrizione completa, esempi (`["id_order", "date_add"]`, `["desc", "asc"]`), nota sul tie-breaker.

**Decisione esplicita sugli indici DB:**
Il task originale chiedeva di "verificare che gli indici DB coprano i nuovi `ORDER BY` … in caso negativo aggiungere migration". Decisione presa: **nessuna migration in questa PR**.
- `orders.id_order` è PK → già indicizzato dal DB. Il default `order_by=id_order desc` (caso d'uso reale: lista ordini "newest first") è quindi già ottimo senza alcun intervento.
- `orders.date_add` NON è indicizzato. Il sort funziona comunque (correttezza ok) ma su tabelle grandi MySQL fa full-table-scan + filesort → query più lente. È **solo una questione di performance**, non di funzionamento.
- Quando/se il FE inizierà a usare massivamente `order_by=date_add` e si misureranno effettivamente query lente, si aggiungerà l'indice in una PR dedicata (1 file Alembic + `index=True` sul modello). Per ora rimandata per evitare modifiche DB premature.

**Decisione esplicita su `date_upd`:**
Il task originale chiedeva di whitelistare anche `date_upd`, ma `Order.updated_at` è dichiarato come `Column(String(19), nullable=True)` con formato `DD-MM-YYYY hh:mm:ss`. L'ordinamento lessicografico su quella stringa NON è temporalmente corretto (sortrebbe per giorno-del-mese prima che per anno). Esporlo darebbe risultati silenziosamente sbagliati. **Escluso dalla whitelist** in questa PR; per abilitarlo serve una PR follow-up che migri `updated_at` a `DateTime` (richiede backfill dei valori esistenti — non banale, fuori scope qui).

**Comportamento finale:**
| Chiamata | Risultato |
|---|---|
| `GET /orders/?date_from=2026-05-08&date_to=2026-05-23&limit=200` | Default `id_order desc` → ordini più recenti in cima (risolve il bug di troncamento FE) |
| `GET /orders/?order_by=date_add&order_direction=asc` | Ordina per data creazione crescente, tie-breaker `id_order asc` |
| `GET /orders/?order_by=date_add&order_direction=DESC` | Accettato (case-insensitive), normalizzato a `desc` |
| `GET /orders/?order_by=foo` | 422 (FastAPI valida `Literal`) |
| `GET /orders/?order_direction=bar` | 422 (validazione manuale nel router) |

**Verifica:**
- ReadLints sui file modificati: nessun errore introdotto.
- Tie-breaker già applicato anche quando `order_by=id_order` (ridondante ma non dannoso).
- Nessuna modifica DB richiesta: PK `id_order` già indicizzato, sort di default già ottimo.
- `uvicorn` server già in esecuzione (terminale 5) — il reload automatico picca le modifiche al router e al repo.

**Coordinamento FE:**
Il FE attualmente fa già una singola chiamata `GET /orders/?order_states_ids=X&...` per tab. Cosa cambia/serve fare lato FE (prompt operativo dedicato già fornito al team FE su repo `webmarke26`):

1. Aggiungere `order_by` / `order_direction` al tipo `GetOrdersQuery` del service HTTP (`OrderSortField = 'id_order' | 'date_add'`, `OrderSortDirection = 'asc' | 'desc'`).
2. Passarli nella chiamata esistente con default `id_order` / `desc`. Questo da solo risolve il bug del "troncamento dei più recenti" sul tab.
3. (Opzionale, consigliato) agganciare `matSort` (o equivalente) sugli header colonna `ID` e `Data` per esporre il sort all'utente.

**Cambio di comportamento osservabile per consumer esistenti:**
Sì. Prima il BE rispondeva ASC implicito, ora risponde DESC implicito. Qualsiasi client che non passa i nuovi param vedrà la lista ribaltata. Per il FE è il comportamento desiderato (era il bug stesso). Se esistono altri consumer (script di sync, integrazioni esterne) che dipendevano implicitamente dall'ordine ASC, devono passare esplicitamente `?order_by=id_order&order_direction=asc` per preservare il vecchio comportamento.

### BE-ORDER-DELETE-500 — Fix 500 su `DELETE /api/v1/orders/{id}` + nuovo contratto FE-ORDER-CANCEL (chiuso 2026-05-26)

**Tipo:** Bug fix + estensione contratto API
**Scope:** Backend
**Priorità:** Alta (bloccante per chiusura FE-ORDER-CANCEL)
**Stima:** ~2h (effettivi)

**Contesto / Trigger:**
Il FE (task `FE-ORDER-CANCEL`) ha implementato 2 azioni separate:
- "Annulla ordine" — cambio stato a 5 via `POST /orders/bulk-status` (reversibile, OK)
- "Elimina ordine" — cancellazione DEFINITIVA via `DELETE /api/v1/orders/{id}` (irreversibile)

Su questa seconda azione il BE rispondeva sistematicamente **500 Internal Server Error** (catturato live il 2026-05-26 14:16 su ordine 69081 dal terminale uvicorn).

**Root cause:**
Stack trace conclusivo:
```
sqlalchemy.exc.IntegrityError: (pymysql.err.IntegrityError) (1451,
'Cannot delete or update a parent row: a foreign key constraint fails
(`ecommerce_manager`.`orders_document`, CONSTRAINT `orders_document_ibfk_7`
 FOREIGN KEY (`id_shipping`) REFERENCES `shipments` (`id_shipping`))')

[SQL: DELETE FROM shipments WHERE shipments.id_shipping IN (79024, 79025, 79023)]
```

`OrderRepository.delete()` nullava `Order.id_shipping` prima del DELETE FROM `shipments`, ma **non `OrderDocument.id_shipping`**. La FK `orders_document_ibfk_7` ha `ON DELETE RESTRICT` lato DB (asimmetria rispetto a `orders_document.id_order` che ha `ON DELETE SET NULL`). L'IntegrityError non era catturata né a livello service né a livello repo → finiva nel `general_exception_handler` come `INTERNAL_ERROR` 500 generico.

**File modificati:**
- `src/repository/order_repository.py` — nuovo **step 6b** in `delete()`: prima della cancellazione delle `Shipping`, esegue `UPDATE orders_document SET id_shipping = NULL WHERE id_shipping IN (shipping_ids_to_delete)`. Docstring del metodo aggiornata per documentare il cleanup di entrambe le FK (`id_order` via DB, `id_shipping` esplicitamente).
- `src/services/routers/order_service.py`:
  - Import aggiunti: `from fastapi import HTTPException, status`, `from sqlalchemy.exc import IntegrityError`.
  - **Rimosso check** `id_order_state != 1`: il DELETE è ora valido in qualsiasi stato (contratto FE-ORDER-CANCEL — protezione UX delegata al dialog warning forte FE-side).
  - **Promosso** il check `FiscalDocument` collegati da `BusinessRuleException` (400) a `HTTPException(409)` con body strutturato `{error_code: "ORDER_HAS_FISCAL_DOCUMENTS", message, details: {order_id, current_state, fiscal_documents_count, fiscal_document_ids}}` (formato proposto dal FE nel prompt operativo). 409 permette al FE di distinguere "errore validazione input" (400) da "conflitto stato risorsa" (409, suggerimento "usa Annulla").
  - **Wrap** della chiamata `repository.delete()` in `try/except IntegrityError`: con rollback esplicito + `HTTPException(409)` con `error_code: "ORDER_DELETE_FK_CONSTRAINT"` + `details.db_error` troncato a 500 char. Difesa in profondità contro FK future non gestite (no più 500 generico).
  - Nota tecnica nel codice: i campi del payload `detail` vanno messi flat (non in sub-chiave `details`) perché `http_exception_handler` in `main.py` ri-incapsula automaticamente sotto `details`.
- `src/routers/order.py` — docstring `delete_order` riscritta con il nuovo contratto: response code 204/404/403/422/409, schema del body 409 per entrambi gli `error_code`, riferimento esplicito a `bulk-status` per il caso "Annulla". OpenAPI/Swagger ora documenta correttamente i nuovi casi.

**Nuovi file:**
- `tests/integration/api/v1/test_order_delete.py` — 5 classi di test, 9 test totali (tutti verdi in 0.80s su SQLite in-memory):
  - `TestOrderDeleteHappyPath` — 4 test: minimal order, stato 3 (verifica rimozione check stato), order con packages+details, **order con `OrderDocument` che condivide `id_shipping`** (riproduzione esatta del bug 69081 — senza il fix 6b solleverebbe 500)
  - `TestOrderDeleteFiscalDocumentsBlock` — 409 + body strutturato verificato campo per campo
  - `TestOrderDeleteNotFound` — 404 su `order_id` inesistente
  - `TestOrderDeleteAuthorization` — 403 `PERMISSION_DENIED` per utente senza `orders.delete`
  - `TestOrderDeleteValidation` — 422 su `order_id <= 0`

**Decisioni di prodotto / contratto (raccolte via questionario operativo 2026-05-26):**
1. **DELETE in qualsiasi stato** (rimosso check `id_order_state == 1`). Per il cambio stato "Annullato" usare `POST /orders/bulk-status` con `id_order_state=5`. Sicurezza affidata al dialog warning forte FE-side.
2. **Strategia fix:** combinazione "Fix bug repo + 409 hardening generico" (non strategia B completa col pre-check di returns/multishipping_with_tracking — rimandata).
3. **Body 409:** formato proposto dal FE nel prompt (`fiscal_documents_count`, `fiscal_document_ids`, ecc.). Difesa in profondità: anche per IntegrityError ignote in futuro → 409 invece di 500.
4. **Use case prioritario:** pulizia operativa di ordini fantasma da PrestaShop/AS400 (uso regolare, non solo test).

**Contratto API finale:**
| Status | error_code | Caso | Body |
|---|---|---|---|
| 204 | — | Success | (no body) |
| 404 | (NotFoundException) | `order_id` inesistente | wrapper standard |
| 403 | PERMISSION_DENIED | No permission `orders.delete` | wrapper standard |
| 422 | — | `order_id <= 0` | FastAPI standard |
| 409 | ORDER_HAS_FISCAL_DOCUMENTS | Ordine con fatture/note di credito | `details: {order_id, current_state, fiscal_documents_count, fiscal_document_ids}` |
| 409 | ORDER_DELETE_FK_CONSTRAINT | IntegrityError residua (FK future ignote) | `details: {order_id, current_state, db_error}` |

**Comportamento FE atteso (da prompt FE):**
- 204 → dispatch `deleteSuccess`, rimuove da lista, chiude modale dettaglio
- 409 ORDER_HAS_FISCAL_DOCUMENTS → alert dedicato col body `details` + suggerimento "usa Annulla ordine"
- 409 ORDER_DELETE_FK_CONSTRAINT → alert "errore residuo" (caso edge, segnalare al BE per cleanup mancante)
- 403/404 → toast esistenti via ErrorInterceptor

**Verifica:**
- ✅ Stack trace originale catturato dal terminale uvicorn `terminals/3.txt` riga 336-492 (bug confermato)
- ✅ 9/9 integration test verdi in 0.80s
- ✅ `ReadLints` su 4 file modificati: zero errori
- ✅ Mappa completa FK in entrata su `orders.id_order` e `shipments.id_shipping` documentata nel prompt risposta (no altri cleanup mancanti)
- ⏳ Smoke test su DB reale (DELETE 69081) demandato all'operatore — vecchia istanza uvicorn da killare (PID 18120) prima del restart con il fix caricato

**Coordinamento FE:**
Sblocca la chiusura del task FE-ORDER-CANCEL — il FE può ora chiamare `DELETE /api/v1/orders/{id}` con la confidenza che:
- Il happy path (ordine senza fatture, qualunque stato) ritorna 204
- Il caso fatturato ritorna 409 con body strutturato per dialog informativo
- Il caso permessi è coerente con gli altri endpoint (403 + PERMISSION_DENIED)

---

## 🟦 Backlog aperto

### Backend — debito tecnico VIES / Tax

> **Programma operativo:** [.cursor/tasks_claude/PROGRAMMA_BE_aliquote_vies.md](.cursor/tasks_claude/PROGRAMMA_BE_aliquote_vies.md)  
> Ordine: BE-ALIQ-00 → 01 (wiring resolver, **bloccante**) → 02 → 08 → 03 → 04 → [07 API] → 05 → 06

#### BE-ALIQ-01 / 01M — VIES non invasiva (✅ chiuso 2026-06-03)

**Scope:** Solo `apply-vies-exemption` (KO→OK) + `POST /orders` con `vies_status=eligible` esplicito. Sync PS invariato (no resolver VIES).  
**Codice:** `tax_resolution.py`, `order_service`, `order_repository.create` / `generate_shipping`.  
**BE-ALIQ-01S annullato** (non modificare regole sync attuali).

#### BE-ALIQ-02 — Delete Tax errore strutturato `TAX_IN_USE`

**Tipo:** Feature  
**Scope:** Backend  
**Priorità:** Alta  
**Stima:** 4–6 h

#### BE-ALIQ-03 / 04 / 06 / 07 — Cache init, serializzazione `id_country`, seed CI, consolidamento API

Dettaglio in `PROGRAMMA_BE_aliquote_vies.md`.

#### BE-TAX-DECIMAL — Tax.percentage Integer → Numeric(5,2)

**Tipo:** Bug fiscale / debito tecnico  
**Scope:** Backend  
**Priorità:** Bassa (rilevante solo per FI 25.5% B2C; il VIES azzera i casi B2B intra-UE)  
**Stima:** 2-3 ore (migration + adeguamento consumatori di `Tax.percentage`)

**Problema:** la colonna `Tax.percentage` è `Integer`, impedisce aliquote decimali (es. Finlandia 25.5%). Il seed BE-VIES-1 ha usato FI=25%.

**Soluzione:** migrare colonna a `Numeric(5,2)`, adeguare schemi Pydantic, verificare calcoli IVA in order_repository, prestashop_service, fiscal_document, fatturapa, csv_import, plugin AS400.

#### BE-TAX-DEFINE-FIX — Riparazione `define_tax` (non bloccante Fase 2)

**Tipo:** Bug  
**Scope:** Backend  
**Priorità:** Bassa  
**Note:** `TaxRepository.define_tax(country_id)` ignora `country_id` e restituisce il primo `Tax` per `id_tax`. Usato solo in `order_repository` alla creazione shipping ordini manuali — **non blocca** BE-VIES-2 (sync `vies_status` + totali PS). Valutare fix o sostituzione con `get_default_by_country`.

#### BE-INFRA-ALEMBIC — Adozione Alembic come migration tool effettivo

**Tipo:** Infrastruttura  
**Scope:** Backend  
**Priorità:** Bassa  
**Note:** `alembic/versions/` vuoto; schema gestito da `scripts/setup_initial.py`. Task indipendente da VIES.

#### BE-VIES-4 — FatturaPA N3.2 / art. 41 (Fase 4/4)

**Tipo:** Feature  
**Scope:** Backend + FatturaPA  
**Priorità:** Da pianificare dopo Fase 2-3.

### Priorità ALTA

#### FE-4 — Toast successo prematuro (race NgRx)

**Tipo:** Bug architetturale
**Scope:** Frontend
**Priorità:** Alta
**Stima:** 3-5 ore (potenzialmente più con audit completo)

**Problema:**
Service operations (es. `TaxOperationsService`) eseguono `store.dispatch()` seguito immediatamente da `alertService.success()` senza aspettare l'esito dell'effect. Quando il backend ritorna 403, l'utente vede prima il Swal "Successo!", poi il Swal "Permesso negato" dall'ErrorInterceptor.

**File coinvolti (esempi):**
- `src/app/tax/services/tax-operations.service.ts` — 7 punti di success prematuro (create, update, delete, toggleDefault, toggle stato, note, update altro)
- Sospetti simili in altri service operations: `orders`, `quotes`, `ddt`, `customers`

**Pattern problematico:**
```typescript
this.store.dispatch(TaxActions.deleteItem({ id: tax.id_tax }));
this.alertService.success('Aliquota Eliminata!', ...);  // ← OTTIMISTA, BUG
```

**Pattern corretto (3 strategie possibili):**
1. **Local subscribe action result:** iniettare `Actions`, fare `actions$.pipe(ofType(Success, Failure), take(1)).subscribe(...)` nel service operations
2. **Helper riusabile:** funzione `waitForActionResult(actions$, successAction, failureAction): Observable<boolean>` in `core/helpers/`
3. **Effect-side:** spostare i Swal success nei `tap()` degli effect `XxxSuccess$` (richiede payload con info specifiche per ogni action)

**Note:**
- Esiste già un helper `wait()` parzialmente usato in `company-info.component.ts` e `ddt-sender.component.ts` — investigare se centralizzarlo
- 3 pattern coesistono nel codebase (component-side, service-side, effect-side) → caos architetturale
- Audit completo necessario: 2 punti `alertService.success` in component, 18 punti `store.dispatch` con success prematuro, 8 punti `alertService` negli effect

---

### Priorità MEDIA

#### FE-1 — Coerenza tra i 3 file menu

**Tipo:** Pulizia
**Scope:** Frontend
**Priorità:** Media
**Stima:** 30-60 min

**Problema:**
Il progetto ha 3 layout (vertical/sidebar, horizontal-topbar, twocolumn/two-column-sidebar) e ognuno ha il proprio `menu.ts`. Il file master è `src/app/layouts/sidebar/menu.ts`. Gli altri 2 sono disallineati:

- `horizontal-topbar/menu.ts`: manca proprietà `module` su tutte le voci, manca voce `Negozi`
- `two-column-sidebar/menu.ts`: voce "Clienti" duplicata in cima (residuo template Velzon), manca `module`, manca `Negozi`

**File coinvolti:**
- `src/app/layouts/sidebar/menu.ts` (master, da rimuovere voce "Utenti" duplicata con "Permessi & Utenti")
- `src/app/layouts/horizontal-topbar/menu.ts`
- `src/app/layouts/two-column-sidebar/menu.ts`

**Decisione di prodotto:** la voce "Utenti" va RIMOSSA — la gestione utenti è integrata in `/admin/permissions`.

**Verifica:**
- `grep -c "module:" sidebar/menu.ts == horizontal-topbar/menu.ts == two-column-sidebar/menu.ts`
- "Utenti" sparito da tutti i menu
- "Negozi" presente in tutti e 3
- "Clienti" duplicata in cima di two-column-sidebar rimossa

#### FE-5 — Pre-check permessi prima delle scritture

**Tipo:** UX miglioramento
**Scope:** Frontend
**Priorità:** Media
**Stima:** 1-2 ore

**Idea:**
Verificare il permesso lato componente PRIMA di inviare la richiesta HTTP, per evitare il roundtrip al BE su 403.

**Esempio:**
```typescript
if (await this.store.select(hasPermission('orders', 'update')).pipe(take(1)).toPromise()) {
  this.store.dispatch(OrdersActions.updateItem(...));
} else {
  this.alertService.error('Permesso negato', 'Non hai i permessi per questa operazione.');
}
```

**Sinergia con FE-3:** se i bottoni sono già nascosti per chi non ha permessi (FE-3), il pre-check diventa difensivo (es. per chiamate da codice).

#### FE-6 — Form inline carriers_config

**Tipo:** Feature UI
**Scope:** Frontend
**Priorità:** Media
**Stima:** 1-2 ore

**Problema:**
Il form di gestione `carriers_config` è probabilmente integrato in `/carriers`. Va gestito con permessi RBAC.

**File da investigare:**
- `src/app/carriers/components/carrier-config-modal/`

#### FE-8 — Pagina profilo non visualizza messaggi pur con BE 200

**Tipo:** Bug
**Scope:** Frontend
**Priorità:** Media
**Stima:** 1-2 ore

**Problema:**
La pagina profilo dovrebbe mostrare i messaggi personali dell'utente. Il BE risponde 200 ma il FE non li mostra.

**File da investigare:**
- `src/app/pages/extrapages/profile/profile/profile.component.ts`
- `src/app/store/Ecommerce/effetcs/messages.effects.ts`

#### FE-11 (già implementato, da testare) — Reset globale al logout

✅ Implementato. **TEST PENDING** (mai validato manualmente in sessione).

---

### Priorità BASSA

#### FE-10 — PermissionGuard su /apps, /ecommerce, /pages

**Tipo:** Sicurezza
**Scope:** Frontend
**Priorità:** Bassa
**Stima:** 30 min (decisione prodotto + implementazione)

**Problema:**
In `pages-routing.module.ts` c'è un TODO esplicito: le route `/apps`, `/ecommerce`, `/pages` non hanno PermissionGuard. Da definire se è policy "loggato basta" o se vanno mappati su module/action specifici.

**Decisione prodotto necessaria.**

#### FE-12 — Rimuovi duplicato src_backup directive

**Tipo:** Pulizia
**Scope:** Frontend
**Priorità:** Bassa (SKIP)
**Stima:** 1 min

**Status:** **CHIUSO come "no fix"** — backup preservato per motivi storici (decisione 2026-05-13).

#### FE-13 — Hard-block JWT pre-HTTP nel guard

**Tipo:** Sicurezza
**Scope:** Frontend
**Priorità:** Bassa
**Stima:** 30 min

**Idea:**
Oggi `AuthGuard` è permissivo: lascia passare se c'è refresh_token, anche se l'access è scaduto. Lascia fare al JwtInterceptor. Se in futuro si vuole hard-block prima del primo HTTP, è qui che si tocca.

#### BE-1 — Endpoint self-service profilo

**Tipo:** Feature
**Scope:** Backend
**Priorità:** Bassa
**Stima:** 1-2 ore

**Endpoint da aggiungere:**
- `PUT /users/me` — modifica nome, email, phone (no role_id, no password)
- `PUT /users/me/password` — cambio password con verifica vecchia password
- Authorization: SOLO `Depends(get_current_user)`, no `require_permission`

**Vincoli:**
- Schema Pydantic ristretto `UserSelfUpdate` (campi modificabili in self-service)
- Validazione email duplicata
- Hash password con bcrypt o algoritmo equivalente al BE

---

### Task tecnici trasversali

#### FE-REFACT — Refactoring OrderDetailsModalComponent (piano dettagliato in documento separato)

**Tipo:** Refactoring strutturale
**Scope:** Frontend
**Priorità:** Media (debito tecnico significativo)
**Stima:** ~9 PR incrementali, 2-4 sessioni di lavoro distribuite

**Documento di piano:** `REFACTORING_ORDER_DETAILS_MODAL.md`

**Sintesi:**
`OrderDetailsModalComponent` è un monolite (8702 righe TS + 1495 righe HTML) che fa quasi tutto sul dettaglio ordine. Solo ~25% del template usa i componenti `document-*-block` shared già presenti nel progetto. Il piano descrive 9 PR incrementali per:
- Pulizia codice morto (4 componenti orfani in `order-details/components/`)
- Estrazione 2 modali annidati (`MultishipmentModalComponent`, `EditShipmentModalComponent`)
- Creazione 3 nuovi blocchi shared (`document-shipping-details-block`, `document-payment-details-block`, `document-history-timeline-block`)
- Allineamento `fiscal-document-details-modal`, `create-order`, `create-quote` allo stesso pattern
- Cleanup finale cartella `order-details/`

**Risultato atteso:**
- `order-details-modal.component.ts`: da 8702 a ~1800-2500 righe
- `order-details-modal.component.html`: da 1495 a ~350-450 righe
- 3 nuovi shared block riusabili in 4+ moduli

**Vincoli chiave (dal documento):**
- Mantenere flusso NgRx (chiamate API solo via Effects)
- Nuovi blocchi standalone + presentational (solo `@Input`/`@Output`)
- Niente regressioni grafiche (refactoring strutturale, UX invariata)
- Ogni PR mergeable in isolamento

**Compatibilità con fix BUG-010:**
Il fix `extractErrorMessage` applicato in `order-details-modal.component.ts` sui handler `createShipmentFailure` (~riga 960) e in futuro su `createMultishippingLabelFailure` (~riga 8200) **deve essere preservato** durante il refactor. Quando PR 2 (estrazione `MultishipmentModalComponent`) verrà eseguito, il pattern `extractErrorMessage` va trasferito nel nuovo componente.

#### REPLAN-SHIPMENT-WORKFLOW v2 — Ripianificazione flusso ordini (versione semplificata)

**Tipo:** Replanning architetturale + nuove feature
**Scope:** Backend + Frontend
**Priorità:** Alta
**Stima:** ~10-13 ore distribuite in 8 PR

**Documento di piano:** `REPLAN_SHIPMENT_WORKFLOW.md` (v2). Versione storica archiviata: `REPLAN_SHIPMENT_WORKFLOW_v1_archived.md`.

**Sintesi v2 (semplificata):**
Riallineamento del flusso ordini con queste decisioni:
1. **Multispedizione rimossa dal FE** (DB resta intatto, ma niente UI/azioni). Tab, badge, filtri, modali, bottoni multispedizione vengono tutti rimossi.
2. **"Spedizione Confermata" non più irreversibile**. Tutti gli stati permettono qualsiasi transizione manuale.
3. **Modifica spedizione fuori scope** per ora. Decideremo dopo.
4. **Riordino tab** nel FE secondo il flusso logico: In Preparazione → Pronti per la Spedizione → In Attesa → Spediti → Spedizione Confermata → Annullati.
5. **Handler AS400** sposta caso OK → Spediti (3), non più → Pronti (2). Caso NOK: niente rollback, ordine resta in 2.
6. **Feature Borderò** in scope: bottone su tab Spediti, dialog selezione corriere, generazione PDF tabellare lato BE.

**Impatto su task già chiusi:**
- ❌ **FE-AUTOTAB** (chiuso 2026-05-14): deprecato, PR 6 rimuove auto-switch
- ❌ **FE-MULTISHIP-BADGE** (chiuso 2026-05-14): deprecato, PR 2+3 rimuovono badge + filtro + utility
- ✅ **BUG-010 fixes**: preservati
- ✅ **BUG-011** cleanup label: preservato

**8 PR incrementali (vedi documento per dettagli):**
1. Riordino tab + rimozione tab Multispedizione (FE) — 10 min
2. Rimozione filtro/checkbox multispedizione (FE) — 30 min
3. Rimozione badge multispedizione + utility (FE) — 20 min
4. Rimozione UI multispedizione dal modale ordine (FE) — 1-2h
5. "Spedizione Confermata" non più bloccante (FE) — 1h
6. Rimozione auto-switch post-LDV (FE) — 30 min — **🟡 BLOCCANTE per chiudere il bug "stato si ribalta"**, istruzioni operative in `.cursor/tasks_claude/PR6_FE_PATCH_INSTRUCTIONS.md`
7. Modifica handler AS400 (BE) — 1h
8. Borderò backend + frontend — 5-6h

**Avanzamento (aggiornamento 2026-05-21):**
- ✅ **PR BE collaterale chiusa** (vedi `BE-AUTOSTATE` sopra): `src/routers/shipments.py` non aggiorna più automaticamente lo stato a 4/7 dopo creazione spedizione singola o bulk. Aggiunta diagnostica opt-in `ORDER_STATE_AUDIT=1` (`src/core/diagnostics/order_state_audit.py`) e script verifica BE-only (`scripts/verify_order_state.ps1`).
- 🟡 **PR 6 (FE)** ancora aperta su `webmarke26`. Senza PR 6, il "ribalto stato" persiste perché il dispatch FE su `bulkCreateShipmentsSuccess` / `createShipmentSuccess` rifà esplicitamente POST `/orders/bulk-status` con `id_order_state: 4`. Conferma da log uvicorn `terminals/5.txt` (vedi BE-AUTOSTATE).
- ⏳ Cleanup BE residuo non urgente: rimuovere `update_order_status(request.id_order, 7)` da `shipping_service.create_multi_shipment` (riga ~597) — non in uso dopo rimozione FE multispedizione, ma da pulire per coerenza.

#### FE-BORDERO — Feature "Stampa riepilogo" (Borderò spedizioni) — BE + FE coordinato

**Tipo:** Feature
**Scope:** Backend + Frontend
**Priorità:** Alta
**Pianificato:** 2026-05-25
**Stima:** ~6-8h totali (PR 8a BE ~3-4h + PR 8b FE ~3-4h)
**Relazione con REPLAN_SHIPMENT_WORKFLOW.md:** chiude PR 8 del piano replan, split in PR 8a (BE) + PR 8b (FE)

**Descrizione:**
Aggiunta del bottone "Stampa riepilogo" nella tab "Spediti" della lista ordini. Genera un PDF tabellare (formato basato su `Vendite.pdf` di esempio) con tutti gli ordini in stato "Spediti" e tracking valorizzato, filtrati per un corriere selezionato dall'operatore. Dopo conferma esplicita dell'operatore, gli ordini stampati passano automaticamente a stato "Spedizione Confermata" (best-effort).

**Decisioni di prodotto chiave (finalizzate 2026-05-25):**
1. Bottone "Stampa riepilogo" sempre visibile in tab "Spediti" (niente selezione manuale richiesta)
2. Dialog 1: scelta corriere (radio button, mostra TUTTI i corrieri attivi nel DB)
3. Filtro automatico BE: `id_order_state = 3 (Spediti)` AND `id_carrier_api = X` AND `tracking IS NOT NULL`
4. Se nessun ordine idoneo per quel corriere → alert "Nessun ordine X da stampare" + stop
5. Dialog 2: "Sposta a Spedizione Confermata?" [Sì] / [No, solo stampa]
6. Apertura PDF in nuova tab browser + `window.print()` automatico
7. Cambio stato best-effort post-PDF: si applica solo agli ordini effettivamente nel borderò
8. Stato 4 è modificabile dall'operatore (non bloccante)

**Mappatura campi PDF → modello dati (basata sull'esempio Vendite.pdf):**
- **Corriere** → JOIN `shipping.id_carrier_api` su `carrier_api.name`
- **ID** → `shipping.id_shipping` (id locale spedizione)
- **Numero Spedizione** → `shipping.tracking` (AWB del corriere)
- **RIF.** → `order.id_order` (numero ordine interno)
- **Destinatario** → JOIN `order.id_address_delivery` su address (`firstname + lastname` o `company`)
- **Indirizzo** → JOIN su address (`address1 + postcode + city`)
- **Colli** → `COUNT(order_packages.id_order_package)` GROUP BY id_order
- **Peso** → `shipping.weight`
- **C/Ass.** → `order.cash_on_delivery`
- **Articoli** → JOIN su `order_details` (concatenazione `product_name`)

**Formato PDF (basato su Vendite.pdf):**
- Header: ragione sociale + indirizzo + telefono mittente + "Riepilogo spedizioni" + data/ora generazione
- Tabella 10 colonne (vedi mappatura sopra)
- Footer: riga "Firma ________________________" + totali finali (totale spedizioni, totale colli, totale peso)
- Ordinamento: per `shipping.id_shipping` DESC (come nel reference)

**PR 8a — Borderò Backend (~3-4h)**

File da creare:
- `src/services/pdf/bordero_pdf_service.py` (estende `BasePDFService`)
- `src/routers/bordero.py`

Endpoint: `POST /api/v1/bordero/generate`
- Request body: `{ carrier_id: int, update_status: bool }`
- Response: PDF blob (con header opzionale `X-Bordero-Order-Count` con N ordini inclusi)

Logica:
1. Query con JOIN: orders + shipping + address + carrier_api + order_packages + order_details
2. Filtra: `id_order_state = 3` AND `id_carrier_api = carrier_id` AND `tracking IS NOT NULL`
3. Ordina: `shipping.id_shipping DESC`
4. Genera PDF estendendo `BasePDFService` (pattern coerente con `ddt_pdf_service.py`, `preventivo_pdf_service.py`)
5. Se `update_status=true` → cambio stato best-effort post-PDF (log warning se fallisce, ritorna PDF comunque)
6. Auth: `Depends(require_permission("shipments", "create"))` (da confermare durante PR)

**PR 8b — Borderò Frontend (~3-4h)**

File da modificare:
- `src/app/pages/orders/order-list/order-list.component.{ts,html}` — bottone "Stampa riepilogo" in tab Spediti
- `src/app/core/services/orders.service.ts` — metodo `generateBordero(carrierId, updateStatus): Observable<Blob>`
- Eventuali 2 nuovi dialog component o uso di SweetAlert esistente per Dialog 1 + Dialog 2

Pattern di riferimento:
- Blob handling: `quotes.service.ts:downloadPdf(id)`
- Lista corrieri: riuso store `initDataFeature.selectCarrierApis` (già caricato, vedi FE-ORDER-TRACKING-SYNC)
- Apertura PDF: `window.open(URL.createObjectURL(blob))` + script per `window.print()` automatico

Workflow operatore:
1. Click "Stampa riepilogo" → Dialog 1 con radio button corrieri (TUTTI quelli attivi)
2. Conferma Dialog 1 → chiamata API
3. BE filtra ordini idonei → se 0 → alert "Nessun ordine X da stampare" + stop
4. Se ≥1 → Dialog 2 "Sposta a Spedizione Confermata?"
5. Sì → BE genera PDF + cambia stato. No → BE genera solo PDF
6. PDF in nuova tab + print automatico

Dipendenze: PR 8a chiusa

**Vincoli architetturali:**
- Pattern NgRx: chiamata API via service, dispatch action/effect per cambio stato
- Component presentazionali per dialog
- Cambio stato best-effort: anche se update fallisce su alcuni ordini, il PDF è comunque generato (log warning)

**Riferimenti:**
- `Vendite.pdf` (esempio formato) — sessione 2026-05-14
- `REPLAN_SHIPMENT_WORKFLOW_v1_archived.md` sez. 8.3 (specifiche storiche borderò)
- `BRT_API_REFERENCE.md` (per validazioni corriere)
- 4 PDF service esistenti come reference pattern: `base_pdf_service.py`, `ddt_pdf_service.py`, `preventivo_pdf_service.py`, `fiscal_document_pdf_service.py`

---

#### FE-ORDER-CANCEL — Bottone "Annulla ordine" (single) in lista e modale

**Tipo:** Feature UX
**Scope:** Frontend (endpoint BE esistente, da verificare)
**Priorità:** Media
**Pianificato:** 2026-05-25
**Stima:** ~1-2h

**Descrizione:**
Aggiunta del bottone "Annulla" in 2 punti del FE per permettere l'annullamento di un singolo ordine (no bulk):
1. Nella lista ordini, accanto ad ogni riga (es. dropdown azioni o icona dedicata)
2. Nel modale dettaglio ordine (es. nel footer o nella sezione azioni)

L'operazione usa l'endpoint BE esistente di "annulla ordine" (da identificare lato BE, probabilmente cambio stato a 5 Annullati via endpoint esistente).

**Decisioni di prodotto chiave:**
1. Solo ordine singolo (no bulk)
2. Disponibile sia in lista (per riga) sia nel modale dettaglio
3. Warning di conferma esplicito prima dell'operazione (es. SweetAlert "Sei sicuro di voler annullare l'ordine #X? L'azione sposterà l'ordine nello stato 'Annullati'.")
4. Coerente con la regola d'oro REPLAN v2: lo stato 5 (Annullati) è raggiungibile da qualsiasi altro stato (stato 4 non bloccante)

**File da modificare:**
- `src/app/pages/orders/order-list/order-list.component.{ts,html}` — bottone "Annulla" per riga (dropdown azioni o icona)
- `src/app/pages/orders/order-details-modal/order-details-modal.component.{ts,html}` — bottone "Annulla" nel footer/azioni
- `src/app/core/services/orders.service.ts` — verificare se il metodo `cancelOrder(id)` esiste, altrimenti aggiungerlo
- Eventualmente nuovi action/effect nello store Orders se non esistono già

**Vincoli architetturali:**
- Pattern NgRx (dispatch + effect, come da FE-ORDER-DETAILS-EDIT)
- Warning UX con SweetAlert (pattern esistente, vedi `alert.service.ts`)
- Refresh ordini dopo successo (probabilmente via cross-slice reducer come in FE-ORDER-TRACKING-SYNC)
- Gestione errori via `extractErrorMessage` (FE-9 chiuso)

**Dipendenze:**
- Endpoint BE di annullamento ordine (da identificare durante la PR — probabilmente esiste già)
- Permessi RBAC: `orders.update` o action dedicata (da verificare)

**Aggiornamento 2026-05-26 — Sblocco BE per "Elimina ordine" (azione B):**
Il prompt FE distingue 2 azioni: "Annulla" (cambio stato 5 via `POST /orders/bulk-status`, già funzionante) e "Elimina" (cancellazione definitiva via `DELETE /api/v1/orders/{id}`). Quest'ultima rispondeva 500 — risolto con `BE-ORDER-DELETE-500` (vedi sopra). Contratto finale: 204/404/403/422/409. Il caso 409 ha 2 varianti (`ORDER_HAS_FISCAL_DOCUMENTS` con `fiscal_document_ids`, `ORDER_DELETE_FK_CONSTRAINT` con `db_error`). Il FE può ora implementare entrambe le azioni in autonomia.

#### T1 — Aggiornare test infrastructure per nuovo RBAC

**Tipo:** Tecnico / Test
**Scope:** Backend (pytest)
**Priorità:** Media
**Stima:** 3-4 ore

**Stato esistente:**
- `pytest.ini` configurato
- `conftest.py` con fixture (ma legacy: `roles=[{"name": "ADMIN", "permissions": ["C","R","U","D"]}]`)
- 8 test file integration in `tests/integration/api/v1/` (test_auth, test_orders, test_categories, test_addresses, ecc.)
- 18 factory in `tests/factories/`
- 46 test items + 1 errore di collect (`user_client_async` fixture incompleta — manca `yield ac`)

**Cosa fare:**
1. **Fix errore di collect:** completare `user_client_async` fixture
2. **Aggiornare fixture** per il nuovo RBAC: `admin_user` con `role_type='full_crud'`, `manager_user` con `role_type='custom'`, popolare `user_module_permissions` di test
3. **Scrivere `test_permissions.py`** per validare la migrazione RBAC: bypass full_crud, accesso negato per permission_zero, accesso negato per module_not_found, self-read di `GET /users/{id}` deprotezionato
4. **Valutare** SQLite vs MySQL per i test (RBAC usa query relazionali complesse)

---

## 🌟 Epic / Feature future

### N1 — Multi-tenant per Partita IVA

**Tipo:** Epic (decine di task)
**Scope:** Backend + Frontend + Database
**Priorità:** Alta (definizione di prodotto necessaria)
**Stima:** Settimane

**Descrizione:**
Selettore bandierina nel topbar per cambiare contesto P.IVA (italiana, francese, estera). Setta configurazioni di funzionamento secondo il flusso fiscale del paese.

**Decisioni di prodotto in sospeso:**
1. Le 3 P.IVA fanno lo stesso business? (impatta condivisione clienti/prodotti)
2. Un operatore lavora su quante P.IVA?
3. Clienti acquistano da più P.IVA? (anagrafica condivisa o separata)
4. Magazzini fisicamente distinti?
5. Ordini convertibili tra P.IVA?

**Strategie tecniche da valutare:**
- **A — Schema-per-tenant:** 3 DB separati. Isolamento totale.
- **B — Discriminator column:** `id_company` su ogni tabella. DB unico, filter automatico.
- **C — Configurazione separata, dati condivisi (ibrido):** solo `app_configurations` e simili sono per-tenant. Pattern Cassel/Danea/Mexal.

**Sotto-domini impattati:** auth, fatturazione, sezionali numerazione, taxes, configurazioni, magazzini, sectional, piattaforme.

### N2 — Sistema notifiche (campanella topbar)

**Tipo:** Epic
**Scope:** Backend + Frontend + Database
**Priorità:** Media
**Stima:** 1-2 settimane

**Descrizione:**
Campanella nel topbar mostra notifiche di eventi silenti (nuovo ordine da piattaforma, fattura emessa, stock basso, errore sync SDI, ecc.).

**Schema DB atteso:**
```sql
notifications (id_notification, id_user, id_event_type, title, message, link, is_read, is_dismissed, created_at, read_at)
notification_event_types (id_event_type, code, description, default_icon, default_priority)
```

**Endpoint BE atteso:**
- `GET /notifications/me` — Lista paginata
- `GET /notifications/me/unread-count` — Badge counter
- `PUT /notifications/{id}/read`
- `POST /notifications/me/mark-all-read`
- `DELETE /notifications/{id}` — Dismissa

**Decisioni prodotto in sospeso:**
1. **Strategia delivery:** Pull periodico (60s), SSE/WebSocket (real-time), Polling lazy (solo al click)
2. **Persistenza:** Tutte persistite in DB, solo session, o misto
3. **Categorie eventi:** piattaforma, business interno, sistema, utente-utente, reminder

**Generazione eventi (BE):**
Service interno che crea notifiche dopo operazioni rilevanti (nuovo ordine importato, DDT generato, errore SDI, ecc.). Filtraggio per destinatario in base ai permessi.

---

## 📋 Note operative

### Setup ambiente
- **PC Backend:** `webmarke22` (IP 192.168.130.119:8000)
  - Path: `C:\Users\webmarke22\Documents\progetti\ECommerceManagerAPI`
  - Comando: `uvicorn src.main:app --host 0.0.0.0 --reload`
- **PC Frontend:** `webmarke26`
  - Path: `C:\Users\webmarke26\Desktop\Gestionale 1.0\Angular\creative_light3`
  - Comando: `ng serve` (proxy.conf.json punta a `http://192.168.130.119:8000`)

### Credenziali test
- `enrica` — full_crud admin (bypassa la matrice)
- `test_manager` — Manager Ordini, role_type custom (14/17 moduli con permessi specifici)
- `test_readonly` — sola lettura, role_type custom
- `test_operator` — operatore base

### Sistema RBAC
- 17 moduli BE: orders, customers, products, quotes, payments, fiscal_documents, shipments, shipping, tax, carriers, carriers_config, ddt, settings, users, stores, platforms, returns
- Helper: `require_permission(module, action)` blocca con 403 + body strutturato `{error_code: "PERMISSION_DENIED", message, details: {module, action, reason}, status_code: 403}`
- `reason` può essere: `module_not_found`, `permission_missing`, `permission_zero`
- Bypass via `role_type=full_crud` → ignora matrice

### Working tree FE non committato
Sono presenti modifiche per FE-7, FE-3 wizard (9 step + tax.component.ts), FE-9 (helper + 5 service + 9 effect), FE-11 (meta-reducer + app.module.ts). **Da committare** prima di affrontare nuovi task per sicurezza.
