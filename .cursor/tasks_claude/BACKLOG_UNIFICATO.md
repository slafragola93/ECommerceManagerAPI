# Backlog Unificato — Elettronew Gestionale e-commerce

> Generato il 2026-06-08 dalla fusione di `BACKLOG.md` (PC FE `webmarke26`) e `BACKLOG.md` (PC BE `webmarke22`).
> Aggiornato 2026-06-18: riconciliazione BE vs codice (FastLDV 1/2/EVT ✅, serie BE-ALIQ-02..05 ✅, fix resi ✅).
> Aggiornato 2026-06-16: stampa PDF DDT (BE ✅ Fase 1–2, FE-DDT-PRINT-PDF aperto) → `docs/FE_HANDOFF_DDT_PRINT_PDF.md`.
> Aggiornato 2026-06-15: stampa PDF singolo ordine (BE ✅, FE-ORDER-PRINT-PDF aperto) → `docs/FE_HANDOFF_ORDER_PRINT_PDF.md`.
> Fonte di verità consolidata per proseguire il lavoro su entrambi i PC.

---

## 📊 Sommario stato (riconciliato)

| Area | ✅ Done | 🟦 Backlog aperto | 🌟 Epic |
|---|---|---|---|
| **Backend** | 45+ (…, BE-FASTLDV-1/2, BE-FASTLDV-EVT impl., BE-ALIQ-02..05, BE-RETURN-PRICE-FIX) | 10 (REPLAN-AS400-PR7, BE-FASTLDV-3, BE-FASTLDV-EVT QA, BE-ALIQ-06/07/08, BE-1, BE-TAX-DEFINE-FIX, BE-VIES-4, BE-INFRA-ALEMBIC, T1) | — |
| **Frontend** | 21+ (..., FE-D.4 ✅) | 11 (FE-DDT-PRINT-PDF, FE-ORDER-PRINT-PDF, FE-4, FE-1, FE-5, FE-6, FE-8, FE-10, FE-13, FE-REFACT, T1*) | 2 (N1, N2) |

\* T1 è task BE ma elencato anche lato FE nel backlog storico (test infrastructure condivisa).

---

## 🔴 PRIORITÀ ALTA — Da fare subito

### ~~BE-FASTLDV-1~~ — ✅ CHIUSO (2026-06-09) — GET ordine unificato

**Tipo:** Feature backend
**Scope:** Backend
**PC:** `webmarke22`
**Priorità:** Alta
**Stima:** 3-4 ore
**Documento:** `docs/BE_FASTLDV_INTEGRATION.md`

**Esito:**
Endpoint `GET /api/v1/fastldv/order/{code}` con payload unificato (carrier, shipping, document, lines, validation). Lookup dual: `id_origin` PrestaShop oppure `id_order` se `id_origin=0`. HTTP 200 (stampabile/warning ristampa) e 422 (bloccato con payload completo). Auth `X-FastLDV-Key`, alias `data.legacy` per adapter PHP.

**File BE:** `src/routers/fastldv.py`, `src/services/routers/fastldv_order_service.py`, `src/core/fastldv_auth.py`, `src/schemas/fastldv_schema.py`

**Test:** `tests/unit/services/test_fastldv_order_service.py`, `tests/integration/api/v1/test_fastldv.py`

---

### ~~BE-FASTLDV-2~~ — ✅ CHIUSO (2026-06-09) — notify-print

**Tipo:** Feature backend
**Scope:** Backend
**PC:** `webmarke22`
**Priorità:** Alta
**Stima:** 1-2 ore
**Documento:** `docs/BE_FASTLDV_INTEGRATION.md`

**Esito:**
Endpoint `POST /api/v1/fastldv/notify-print` aggiorna `shipping.tracking` via `orders.id_shipping` (multispedizione accantonata v1). Emit evento `order.tracking.updated` dopo commit (vedi BE-FASTLDV-EVT).

**Test:** `tests/integration/api/v1/test_fastldv.py` (`test_notify_print_200`)

**Prossimo step operativo:** cutover app magazzino (Fase 3, prompt `docs/PROMPT_FASTLDV_APP_CUTOVER.md`) — fuori scope BE core.

---

### BE-FASTLDV-EVT — Emit + SSE tracking post-stampa (Angular real-time)

**Tipo:** Feature backend (+ coordinamento FE Angular)
**Scope:** Backend + FE gestionale
**PC:** `webmarke22` (BE), `webmarke26` (FE)
**Priorità:** Alta — **implementazione ✅, QA congiunto pending**
**Stima residua:** ~2 h QA
**Documento:** `docs/BE_FASTLDV_INTEGRATION.md` § BE-FASTLDV-EVT

**Esito BE (2026-06-11):**
- `EventType.ORDER_TRACKING_UPDATED` + emit in `notify_print` dopo commit
- `SseFanoutService` + `GET /api/v1/events/stream` (SSE, JWT)
- Test: `tests/integration/api/v1/test_events_sse.py`, `tests/unit/events/test_sse_fanout_service.py`
- (FE creative_light3) `OrderEventsService` + NgRx patch tracking — implementato

**Acceptance residua:**
- [ ] QA congiunto BE+FE (checklist `docs/FE_HANDOFF_SSE_TRACKING.md`)

---

### BE-FASTLDV-3 — `PATCH /api/v1/fastldv/order/{code}/shipping-params`

**Tipo:** Feature backend
**Scope:** Backend
**PC:** `webmarke22`
**Priorità:** Media
**Stima:** 1-2 ore
**Dipendenza:** BE-FASTLDV-1 ✅
**Documento:** `docs/BE_FASTLDV_INTEGRATION.md`
**Stato:** **Aperto (opzionale)** — necessario solo se si mantiene modifica colli in modalità Verifica al cutover app

**Contesto:**
Sostituisce `updateOrderData` — solo modalità **Verifica** in `app.js` (`eseguiVerifica`). Body: `colli`, `peso`, `contrassegno`, `rigenera` (0|1).

**Verifica codice (2026-06-18):** endpoint **non implementato** in `src/routers/fastldv.py`.

---

**Acceptance criteria FastLDV (1 + 2):**
- [x] GET unificato: dati spedizione + `lines` + `validation` in una response
- [x] `200` se stampabile (ok o warning ristampa); `422` se bloccato con payload completo
- [x] `validation.code` enum + messaggi IT da `validate.php`
- [x] POST notify-print aggiorna `shipping.tracking`
- [x] Auth `X-FastLDV-Key` implementata
- [x] Test `FastLdvOrderService` + integration API

**Fuori scope iniziale:** `fastldvGetPdfPrint` / generazione ZPL — fase successiva verso API corrieri gestionale. Cutover app magazzino: `docs/PROMPT_FASTLDV_APP_CUTOVER.md`.

---

### ~~BE-VIES-ORDERS-AREA-C~~ — ✅ CHIUSO (2026-06-08)

**Tipo:** Feature backend (scope ridotto)
**Scope:** Backend
**PC:** `webmarke22`

**Esito:**
- `PATCH apply-vies-exemption`, `POST bulk-apply-vies-exemption`, filtro `?vies_status=` — implementati e testati
- Toggle generico `PATCH /orders/{id}/vies-status` **eliminato dallo scope** (flusso solo KO→OK via apply-vies-exemption; revoca non prevista)
- `vies_status` esposto su tutti i DTO ordine (`OrderSimpleResponseSchema`, `OrderResponseSchema`, `OrderIdSchema`)

**Regola FE:** usare sempre `PATCH apply-vies-exemption`, mai `PUT /orders/{id}` con solo `vies_status`.

---

### ~~FE-D.4~~ — ✅ CHIUSO (2026-06-08) — Bulk apply VIES dalla lista ordini

**Tipo:** Feature frontend
**Scope:** Frontend
**PC:** `webmarke26`
**Priorità:** Alta

**Esito:**
Bulk apply esenzione VIES dalla lista ordini integrato con `POST /api/v1/orders/bulk-apply-vies-exemption`.
Apply singolo da modale già OK (`PATCH /orders/{id}/apply-vies-exemption`).

**Contratto bulk (verificato lato BE — vedi `docs/FE_VIES_APPLY_EXEMPTION_BUTTON.md`):**
```http
POST /api/v1/orders/bulk-apply-vies-exemption
Body: { "order_ids": [69099] }
Response 200: { "status": "success", "data": { "processed": 1, "order_ids": [69099] } }
```
Schemi BE: `BulkApplyViesExemptionSchema` (request) / `BulkApplyViesExemptionResponseSchema` (`processed`, `order_ids`). RBAC `orders:update`.

**Verifica `vies_status` su OrderDTO — ✅ OK:**
`vies_status` esposto su tutti i DTO ordine in `src/schemas/order_schema.py`:
- `OrderSimpleResponseSchema` (GET lista) ✓
- `OrderResponseSchema` (response completa) ✓
- `OrderIdSchema` (GET by id) ✓

Il filtro lista può quindi essere fatto client-side.

**Note collegate:**
- Toggle `PATCH /orders/{id}/vies-status` (D.3) **non usato** → D.3 in pausa (revoca/toggle generico non previsto nel flusso corrente, solo KO→OK).

---

### ~~BE-ORDER-PRINT-PDF~~ — ✅ CHIUSO (2026-06-15) — Stampa PDF singolo ordine

**Tipo:** Feature backend
**Scope:** Backend
**PC:** `webmarke22`
**Priorità:** Alta
**Stima:** ~3-4 ore

**Esito:**
Endpoint `GET /api/v1/orders/{id_order}/pdf` con layout elettronew (logo, barcode Code39, Intestazione / Indirizzo di consegna, tabella righe Impon./IVA/Sconto, totali a destra, note).

**File BE:**
- `src/services/pdf/order_pdf_service.py`
- `src/services/routers/order_service.py` → `generate_order_pdf`
- `src/routers/order.py` → `download_order_pdf`

**Contratto:**
- RBAC: `orders.read`
- Response: `application/pdf`, `Content-Disposition: inline; filename="Ordine-{id_order}.pdf"`
- Identificatore path: sempre **`id_order`** (PK gestionale)

**Handoff FE:** `docs/FE_HANDOFF_ORDER_PRINT_PDF.md` · prompt chat: `.cursor/tasks_claude/prompt_FE_order_print_pdf.md`

---

### BE-DDT-PRINT-PDF ✅ — Fix + PDF DDT (Fase 1–2)

**Tipo:** Bugfix + hardening backend
**Scope:** Backend
**PC:** `webmarke22`
**Priorità:** Alta
**Stima:** ~2–3 ore
**Stato:** ✅ Chiuso 2026-06-16 (Fase 1–2). Fase 3 BE (test integrazione opz.) rimandata.

**Esito:**
Endpoint `GET /api/v1/ddt/pdf/{id_order_document}` operativo. Fix 500 (`Decimal` vs `float`), IVA righe via `TaxRepository`, sconti riga, colli da `packages`, router con error handling strutturato.

**File BE:**
- `src/services/pdf/ddt_pdf_service.py`
- `src/services/routers/ddt_service.py` → `generate_ddt_pdf`, shipping float + `vat_percentage`
- `src/routers/ddt.py` → `generate_ddt_pdf`

**Contratto:**
- RBAC: `ddt.read`
- Response: `application/pdf`, `Content-Disposition: attachment; filename="DDT-{document_number}.pdf"`
- Identificatore path: sempre **`id_order_document`** (PK documento)

**Handoff FE:** `docs/FE_HANDOFF_DDT_PRINT_PDF.md` · prompt chat: `.cursor/tasks_claude/prompt_FE_ddt_print_pdf.md`

---

### FE-DDT-PRINT-PDF — Bottone «Stampa DDT» (dettaglio documento)

**Tipo:** Feature frontend
**Scope:** Frontend
**PC:** `webmarke26`
**Priorità:** Alta
**Stima:** 1–2 ore
**Dipendenza:** BE-DDT-PRINT-PDF ✅ (Fase 1–2)
**Documento:** `docs/FE_HANDOFF_DDT_PRINT_PDF.md`
**Prompt sessione:** `.cursor/tasks_claude/prompt_FE_ddt_print_pdf.md`

**Contesto:**
Il BE genera il PDF DDT (mittente, destinatario, articoli, IVA, spedizione, colli). Il FE scarica blob e apre nuova tab (pattern preventivo / ordine).

**API:**
```http
GET /api/v1/ddt/pdf/{id_order_document}
Authorization: Bearer <JWT>
→ 200 application/pdf (attachment)
```

**Task FE:**
1. `ddt.service.ts` → `downloadDdtPdf(id_order_document): Observable<Blob>` (`responseType: 'blob'`)
2. Bottone toolbar dettaglio DDT — «Stampa DDT» (icona `print`)
3. `URL.createObjectURL` + `window.open`; fallback download se popup blocker
4. Gestione errori 404/500 su risposta blob (parse JSON da `Blob`)
5. **Non** usare `id_order` nel path PDF
6. (Opzionale) voce menu lista DDT; (opzionale) `window.print()` auto

**Pattern da riusare:**
- `quotes.service.ts` → `downloadPdf(id)`
- `orders.service.ts` → `downloadOrderPdf(id)` / `generateBordero(...)`

**Acceptance criteria:**
- [ ] Click stampa → PDF in nuova tab, layout completo
- [ ] Usa `id_order_document`, non `id_order` / `document_number`
- [ ] 404/500 con messaggio utente
- [ ] Loading / no doppio click
- [ ] Nessuna regressione stampa preventivo / ordine / borderò

---

### FE-ORDER-PRINT-PDF — Bottone «Stampa ordine» (modale dettaglio)

**Tipo:** Feature frontend
**Scope:** Frontend
**PC:** `webmarke26`
**Priorità:** Alta
**Stima:** 1-2 ore
**Dipendenza:** BE-ORDER-PRINT-PDF ✅
**Documento:** `docs/FE_HANDOFF_ORDER_PRINT_PDF.md`
**Prompt sessione:** `.cursor/tasks_claude/prompt_FE_order_print_pdf.md`

**Contesto:**
Il BE genera il PDF ordine (layout cartaceo elettronew). Il FE **non** compone più HTML di stampa: scarica blob e apre nuova tab (pattern già usato per preventivo / borderò).

**API:**
```http
GET /api/v1/orders/{id_order}/pdf
Authorization: Bearer <JWT>
→ 200 application/pdf (inline)
```

**Task FE:**
1. `orders.service.ts` → `downloadOrderPdf(id_order): Observable<Blob>` (`responseType: 'blob'`)
2. Bottone toolbar modale dettaglio ordine — «Stampa ordine» (icona `print`)
3. `URL.createObjectURL` + `window.open`; fallback download se popup blocker
4. Gestione errori 404/500 su risposta blob (parse JSON da `Blob`)
5. (Opzionale) voce menu lista ordini; (opzionale) `window.print()` auto come borderò

**Pattern da riusare:**
- `quotes.service.ts` → `downloadPdf(id)`
- `orders.service.ts` → `generateBordero(...)` + apertura tab

**Acceptance criteria:**
- [ ] Click stampa → PDF in nuova tab, layout completo (logo, righe, totali)
- [ ] Usa `id_order`, non `id_origin`
- [ ] 404/500 con messaggio utente
- [ ] Loading / no doppio click
- [ ] Nessuna regressione stampa preventivo / borderò

---

### FE-4 — Toast successo prematuro (race NgRx)

**Tipo:** Bug architetturale
**Scope:** Frontend
**PC:** `webmarke26`
**Priorità:** Alta
**Stima:** 3-5 ore

**Problema:**
Service operations (es. `TaxOperationsService`) eseguono `store.dispatch()` seguito immediatamente da `alertService.success()` senza aspettare l'esito dell'effect. Quando il backend ritorna 403, l'utente vede prima il Swal "Successo!", poi il Swal "Permesso negato".

**Pattern problematico:**
```typescript
this.store.dispatch(TaxActions.deleteItem({ id: tax.id_tax }));
this.alertService.success('Aliquota Eliminata!', ...); // ← OTTIMISTA, BUG
```

**Pattern corretto (3 strategie):**
1. Local subscribe action result: `Actions` + `ofType(Success, Failure)` + `take(1)`
2. Helper riusabile `waitForActionResult(actions$, successAction, failureAction)`
3. Effect-side: spostare i Swal success nei `tap()` degli effect `XxxSuccess$`

**File coinvolti:**
- `src/app/tax/services/tax-operations.service.ts` — 7 punti di success prematuro
- Sospetti simili: service operations per `orders`, `quotes`, `ddt`, `customers`
- Esiste già helper `wait()` in `company-info.component.ts` e `ddt-sender.component.ts` — valutare centralizzazione

---

### REPLAN-AS400-PR7 — Modifica handler AS400 (unica PR aperta REPLAN v2)

**Tipo:** Feature backend
**Scope:** Backend
**PC:** `webmarke22`
**Priorità:** Alta
**Stima:** ~1 ora
**Stato:** **Aperto** — codice non ancora allineato

Handler AS400 caso OK: sposta ordine a stato **3 (Spediti)**, non più a 2 (Pronti per la Spedizione).
Handler AS400 caso NOK: niente rollback, ordine resta in stato 2.

**Verifica codice (2026-06-18):** `validation_handler.py` conferma ancora stato **2** su OK e fa rollback a **1** su NOK/errore.

**File:** `src/events/plugins/customs/as400_validate_order_megawatt/handlers/validation_handler.py`

---

### ~~BE-RETURN-PRICE-FIX~~ — ✅ CHIUSO (2026-06-16) — Fix calcolo righe reso (doppia IVA)

**Tipo:** Bugfix backend
**Scope:** Backend
**PC:** `webmarke22`
**Priorità:** Alta

**Problema:** in creazione/aggiornamento reso, se il FE inviava `unit_price` con importo **con IVA** dell'ordine, il BE lo trattava come imponibile e ricalcolava l'IVA (totale errato).

**Esito:** helper `resolve_return_unit_prices` in `src/services/core/tool.py`; applicato in `FiscalDocumentService`, `FiscalDocumentRepository` (create/update/totali).

**Test:** `tests/unit/services/core/test_resolve_return_unit_prices.py`

---

## 🟡 PRIORITÀ MEDIA — Da pianificare

### BE-ALIQ-06/07/08 — Completamento serie aliquote (residuo)

**Tipo:** Feature / Debito tecnico
**Scope:** Backend
**PC:** `webmarke22`
**Priorità:** Media
**Programma:** `PROGRAMMA_BE_aliquote_vies.md`

**Chiusi (2026-06-05, verificati in codice):**
- ~~**BE-ALIQ-02:**~~ delete Tax `TAX_IN_USE` strutturato (`tax_usages.py`, test integration)
- ~~**BE-ALIQ-03:**~~ invalidazione cache `/api/v1/init/` su write Tax/Settings (`invalidate_init_data_cache`)
- ~~**BE-ALIQ-04:**~~ serializzazione `id_country` nullable (`serialize_tax_response`, test schema)
- ~~**BE-ALIQ-05:**~~ migrazione `Tax.percentage` → `DECIMAL(5,2)` (modello + setup idempotente)

**Ancora aperti:**
- **BE-ALIQ-06:** seed aliquote dedicato CI/testing (oggi solo `SEED_EU_VAT_TAXES=1` opzionale in `setup_initial.py`)
- **BE-ALIQ-07:** consolidamento API Tax (review endpoint, documentazione OpenAPI)
- **BE-ALIQ-08:** pulizia codice residuo multispedizione — **`shipping_service.py:597`** (`update_order_status(..., 7)`) ancora presente

**Ordine suggerito:** `08 → 06 → 07`

---

### FE-1 — Coerenza tra i 3 file menu

**Tipo:** Pulizia
**Scope:** Frontend
**PC:** `webmarke26`
**Priorità:** Media
**Stima:** 30-60 min

3 layout (vertical/sidebar, horizontal-topbar, twocolumn) con `menu.ts` disallineati.
- `horizontal-topbar/menu.ts`: manca `module` su tutte le voci, manca voce `Negozi`
- `two-column-sidebar/menu.ts`: voce "Clienti" duplicata, manca `module`, manca `Negozi`
- `sidebar/menu.ts` (master): rimuovere voce "Utenti" (gestione integrata in `/admin/permissions`)

---

### FE-5 — Pre-check permessi prima delle scritture

**Tipo:** UX miglioramento
**Scope:** Frontend
**PC:** `webmarke26`
**Priorità:** Media
**Stima:** 1-2 ore

Verificare il permesso lato componente PRIMA di inviare la richiesta HTTP. Sinergia con FE-3 (bottoni già nascosti). Utile come difesa per chiamate da codice.

---

### FE-6 — Form inline carriers_config con permessi RBAC

**Tipo:** Feature UI
**Scope:** Frontend
**PC:** `webmarke26`
**Priorità:** Media
**Stima:** 1-2 ore

Gestione `carriers_config` integrata in `/carriers` con protezione RBAC. Investigare `src/app/carriers/components/carrier-config-modal/`.

---

### FE-8 — Pagina profilo non visualizza messaggi (BE risponde 200)

**Tipo:** Bug
**Scope:** Frontend
**PC:** `webmarke26`
**Priorità:** Media
**Stima:** 1-2 ore

File da investigare:
- `src/app/pages/extrapages/profile/profile/profile.component.ts`
- `src/app/store/Ecommerce/effetcs/messages.effects.ts`

---

### FE-REFACT — Refactoring OrderDetailsModalComponent

**Tipo:** Refactoring strutturale
**Scope:** Frontend
**PC:** `webmarke26`
**Priorità:** Media
**Stima:** ~9 PR incrementali, 2-4 sessioni
**Documento di piano:** `REFACTORING_ORDER_DETAILS_MODAL.md`

`OrderDetailsModalComponent` è un monolite (8702 righe TS + 1495 righe HTML). Piano in 9 PR per estrarre modali annidati, creare 3 blocchi shared, allineare i moduli correlati.
Risultato atteso: da 8702 a ~1800-2500 righe TS.
**Vincolo:** preservare il fix `extractErrorMessage` (FE-9) durante l'estrazione di `MultishipmentModalComponent`.

---

### T1 — Aggiornare test infrastructure per nuovo RBAC

**Tipo:** Tecnico / Test
**Scope:** Backend
**PC:** `webmarke22`
**Priorità:** Media
**Stima:** 3-4 ore
**Stato:** **Parzialmente aperto**

**Verifica codice (2026-06-18):**
- [x] Fixture `user_client_async` completa (`yield ac` presente in `tests/conftest.py`)
- [ ] Fixture RBAC centralizzate: `admin_user` in conftest usa ancora schema legacy (`roles[].permissions`), non `role_type='full_crud'` / `custom` come in produzione
- [ ] `test_permissions.py` dedicato — **assente** (403 bypass/negato non coperti in un unico modulo)
- [ ] Valutare SQLite vs MySQL per i test

**Nota:** diversi test integration usano già override locali `_admin_full_crud_user()` (es. `test_bordero.py`, `test_tax_delete.py`); manca consolidamento in conftest.

---

## 🔵 PRIORITÀ BASSA — Debito tecnico

### ~~BE-TAX-DECIMAL~~ — ✅ CHIUSO (2026-06-05) — come BE-ALIQ-05

**Tipo:** Debito tecnico
**Scope:** Backend
**PC:** `webmarke22`

**Esito:** colonna `taxes.percentage` → `DECIMAL(5,2)`; schema API `Decimal`; seed Finlandia 25.5%; setup idempotente in `scripts/setup_initial.py`. Test integration `test_tax_percentage_decimal.py`.

**Verifica operativa residua (non bloccante):** su ambienti legacy eseguire `python scripts/check_tax_percentage_column.py` se PUT/POST tronca i decimali.

---

### BE-TAX-DEFINE-FIX — Riparazione `define_tax`

**Tipo:** Bug (non bloccante)
**Scope:** Backend
**PC:** `webmarke22`
**Stato:** **Aperto**

`TaxRepository.define_tax(country_id)` ignora `country_id` e restituisce il primo `Tax` per `id_tax`. Valutare fix o sostituzione con `get_default_by_country` / `get_tax_info_by_country`.

**Verifica codice (2026-06-18):** bug ancora presente in `src/repository/tax_repository.py:55-67`. Usato da `order_repository.py`.

---

### BE-1 — Endpoint self-service profilo utente

**Tipo:** Feature
**Scope:** Backend
**PC:** `webmarke22`
**Stima:** 1-2 ore
**Stato:** **Aperto** — sblocca FE-8

- `PUT /users/me` — modifica nome, email, phone. Schema `UserSelfUpdate`.
- `PUT /users/me/password` — cambio password con verifica vecchia. Hash bcrypt.
- Auth: solo `Depends(get_current_user)`, no `require_permission`.

**Verifica codice (2026-06-18):** nessun endpoint `/users/me` in `src/routers/`.

---

### BE-VIES-4 — FatturaPA N3.2 / art. 41 (Fase 4/4)

**Tipo:** Feature
**Scope:** Backend + FatturaPA
**PC:** `webmarke22`
**Priorità:** Da pianificare
**Stato:** **Aperto**

Integrazione natura **`N3.2`** (art. 41 DL 331/93) nella generazione FatturaPA per ordini `vies_status = eligible`.

**Verifica codice (2026-06-18):** `fatturapa_service.py` usa `tax.electronic_code` generico, non ramo VIES/N3.2 su `vies_status`. Validator accetta N1–N7 ma nessuna logica business collega ordine eligible → N3.2.

---

### BE-INFRA-ALEMBIC — Adozione Alembic come migration tool effettivo

**Tipo:** Infrastruttura
**Scope:** Backend
**PC:** `webmarke22`
**Stato:** **Parzialmente aperto**

Alembic configurato (`alembic/env.py`) ma **`alembic/versions/` è in `.gitignore`** — le revisioni non sono versionate nel repo. Schema baseline ancora da `scripts/setup_initial.py` + migration locali non condivise.

**Task residuo:** committare revisioni (rimuovere da gitignore o policy alternativa), baseline documentata, `alembic upgrade head` come unico path deploy.

---

### FE-10 — PermissionGuard su /apps, /ecommerce, /pages

**Tipo:** Sicurezza
**Scope:** Frontend
**PC:** `webmarke26`
**Stima:** 30 min

Decisione di prodotto necessaria: "loggato basta" o mapping su module/action specifici.

---

### FE-13 — Hard-block JWT pre-HTTP nel guard

**Tipo:** Sicurezza
**Scope:** Frontend
**PC:** `webmarke26`
**Stima:** 30 min

`AuthGuard` attuale permissivo: lascia passare se c'è `refresh_token` anche se l'access è scaduto.

---

## 🌟 Epic / Feature future

### N1 — Multi-tenant per Partita IVA

**Tipo:** Epic
**Scope:** Backend + Frontend + Database
**Stima:** Settimane — decisioni di prodotto necessarie

Selettore bandierina nel topbar per cambiare contesto P.IVA. Strategie: schema-per-tenant, discriminator column `id_company`, o config separata + dati condivisi (ibrido Cassel/Danea).

---

### N2 — Sistema notifiche (campanella topbar)

**Tipo:** Epic
**Scope:** Backend + Frontend + Database
**Stima:** 1-2 settimane

Campanella notifiche eventi silenti (nuovo ordine, fattura emessa, stock basso, errore SDI). Decisioni aperte: delivery (pull 60s / SSE / polling lazy), persistenza, categorie eventi.

---

## 📋 Note operative

### Setup ambiente
- **PC Backend `webmarke22`:** `C:\Users\webmarke22\Documents\progetti\ECommerceManagerAPI`
  Comando: `uvicorn src.main:app --host 0.0.0.0 --reload` (porta 8000)
- **PC Frontend `webmarke26`:** `C:\Users\webmarke26\Desktop\Gestionale 1.0\Angular\creative_light3`
  Comando: `ng serve` (proxy.conf.json → `http://192.168.130.119:8000`)

### Credenziali test
- `enrica` — full_crud admin (bypassa la matrice RBAC)
- `test_manager` — Manager Ordini, role_type custom (14/17 moduli)
- `test_readonly` — sola lettura
- `test_operator` — operatore base

### Sistema RBAC
- 17 moduli: `orders, customers, products, quotes, payments, fiscal_documents, shipments, shipping, tax, carriers, carriers_config, ddt, settings, users, stores, platforms, returns`
- Helper: `require_permission(module, action)` → 403 + body strutturato
- Bypass: `role_type=full_crud`

### Pattern architetturali obbligatori
- **BE:** Router → Service → Repository → Model; DI via `src/core/container.py`
- **FE:** Component → dispatch → Effect → Service → Reducer → Selector; zero HTTP nei component

### Integrazione FastLDV (magazzino)
- **Doc:** `docs/BE_FASTLDV_INTEGRATION.md` — contratto da `app.js` / `validate.php`
- **BE core:** ✅ `BE-FASTLDV-1/2` (GET unificato + notify-print), ✅ `BE-FASTLDV-EVT` (SSE)
- **Aperto BE:** `BE-FASTLDV-3` opz. (`PATCH shipping-params`); QA congiunto SSE
- **Cutover app magazzino:** Fase 3 — `docs/PROMPT_FASTLDV_APP_CUTOVER.md` (adapter PHP, fuori repo BE)
- **ID API:** `id_origin` (PrestaShop); auth `X-FastLDV-Key`

### Stampa PDF ordine (gestionale Angular)
- **BE:** ✅ `GET /api/v1/orders/{id_order}/pdf` — layout elettronew server-side
- **FE:** task **FE-ORDER-PRINT-PDF** (bottone modale dettaglio)
- **Doc:** `docs/FE_HANDOFF_ORDER_PRINT_PDF.md` · prompt: `.cursor/tasks_claude/prompt_FE_order_print_pdf.md`

### Stampa PDF DDT (gestionale Angular)
- **BE:** ✅ `GET /api/v1/ddt/pdf/{id_order_document}` — fix 500 + IVA/colli (Fase 1–2, 2026-06-16)
- **FE:** task **FE-DDT-PRINT-PDF** (bottone dettaglio DDT)
- **Doc:** `docs/FE_HANDOFF_DDT_PRINT_PDF.md` · prompt: `.cursor/tasks_claude/prompt_FE_ddt_print_pdf.md`

### Principio VIES (vincolante)
La logica VIES è **non invasiva**. Si attiva solo in due punti espliciti:
- Rettifica manuale KO→OK: `PATCH apply-vies-exemption` → righe a 0%, totale ivato invariato
- Creazione esplicita: `POST /orders` con `vies_status: eligible` → righe senza `id_tax` ricevono aliquota VIES

**Regola FE:** usare sempre `PATCH apply-vies-exemption`, mai `PUT /orders/{id}` con solo `vies_status`.
La sync PrestaShop resta invariata: solo snapshot informativo di `vies_status`, nessun ricalcolo prezzi.

### Debiti tecnici noti trasversali
- `BE-ALIQ-08` (bassa): rimuovere `update_order_status(request.id_order, 7)` da `shipping_service.py:597` — **ancora presente**
- `BE-TAX-DEFINE-FIX`: `define_tax(country_id)` ignora il paese — **ancora presente**
- Test VIES rapido: `pytest tests/unit/vies/ tests/unit/services/test_tax_service.py tests/unit/services/test_order_vies_exemption.py tests/unit/repository/test_order_create_vies_eligible_tax.py -v`
- Test FastLDV: `pytest tests/unit/services/test_fastldv_order_service.py tests/integration/api/v1/test_fastldv.py tests/integration/api/v1/test_events_sse.py -v`

---

## 📝 Changelog

| Data | Evento |
|---|---|
| 2026-06-18 | Riconciliazione backlog vs codice: chiusi BE-FASTLDV-1/2, BE-FASTLDV-EVT (impl.), BE-ALIQ-02..05, BE-TAX-DECIMAL, BE-RETURN-PRICE-FIX. Aggiornati stati REPLAN-AS400-PR7, BE-1, BE-VIES-4, T1, BE-INFRA-ALEMBIC |
| 2026-06-16 | BE-RETURN-PRICE-FIX ✅: `resolve_return_unit_prices` — fix doppia IVA su righe reso |
| 2026-06-16 | BE-DDT-PRINT-PDF ✅ Fase 1–2: fix PDF DDT (`Decimal`/IVA/colli), test unit `test_ddt_pdf_service.py`. Handoff FE `docs/FE_HANDOFF_DDT_PRINT_PDF.md`. Aperto **FE-DDT-PRINT-PDF** |
| 2026-06-15 | BE-ORDER-PRINT-PDF ✅: `GET /orders/{id}/pdf`, `OrderPDFService`, handoff FE `docs/FE_HANDOFF_ORDER_PRINT_PDF.md`. Aperto FE-ORDER-PRINT-PDF (bottone stampa modale) |
| 2026-06-09 | BE-FASTLDV: endpoint unificato GET order (dati+validate+righe), `validation.code`, 422 con payload completo. Task 1/2/3. Doc + prompt aggiornati |
| 2026-06-09 | BE-FASTLDV: contratto iniziale da `app.js` + `validate.php`, `id_origin`. Doc `docs/BE_FASTLDV_INTEGRATION.md` |
| 2026-06-08 | FE-D.4 chiuso: bulk apply VIES dalla lista ordini su `POST /bulk-apply-vies-exemption` (contratto `{status,data:{processed,order_ids}}`). Apply singolo OK. Toggle PATCH vies-status non usato (D.3 in pausa). Verificato `vies_status` su tutti i DTO ordine (lista + by id) |
| 2026-06-08 | Aggiornamento con recap BE VIES/ALIQ: BE-ALIQ-00/02, BE-TAX-DECIMAL@modello, filtro vies_status lista, delete TAX_IN_USE marcati come chiusi |
| 2026-06-08 | Aggiunti BE-FASTLDV-1/2 (integrazione app magazzino) |
| 2026-06-08 | BE-VIES-ORDERS-AREA-C chiuso: toggle singolo vies_status eliminato dallo scope (flusso solo KO→OK, revoca non prevista) |
| 2026-06-08 | Creazione backlog unificato da fusione FE+BE |
