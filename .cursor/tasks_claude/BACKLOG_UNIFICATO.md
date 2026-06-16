# Backlog Unificato — Elettronew Gestionale e-commerce

> Generato il 2026-06-08 dalla fusione di `BACKLOG.md` (PC FE `webmarke26`) e `BACKLOG.md` (PC BE `webmarke22`).
> Aggiornato 2026-06-16: stampa PDF DDT (BE ✅ Fase 1–2, FE-DDT-PRINT-PDF aperto) → `docs/FE_HANDOFF_DDT_PRINT_PDF.md`.
> Aggiornato 2026-06-15: stampa PDF singolo ordine (BE ✅, FE-ORDER-PRINT-PDF aperto) → `docs/FE_HANDOFF_ORDER_PRINT_PDF.md`.
> Fonte di verità consolidata per proseguire il lavoro su entrambi i PC.

---

## 📊 Sommario stato (riconciliato)

| Area | ✅ Done | 🟦 Backlog aperto | 🌟 Epic |
|---|---|---|---|
| **Backend** | 37+ (..., BE-DDT-PRINT-PDF ✅ Fase 1–2) | 6 (BE-FASTLDV-1/2/3, BE-VIES-4, BE-ALIQ-03..08, BE-1, BE-TAX-DEFINE-FIX, BE-INFRA-ALEMBIC, REPLAN-AS400-PR7) | — |
| **Frontend** | 21+ (..., FE-D.4 ✅) | 11 (FE-DDT-PRINT-PDF, FE-ORDER-PRINT-PDF, FE-4, FE-1, FE-5, FE-6, FE-8, FE-10, FE-13, FE-REFACT, T1) | 2 (N1, N2) |

---

## 🔴 PRIORITÀ ALTA — Da fare subito

### BE-FASTLDV-1 — `GET /api/v1/fastldv/order/{code}` (unificato: dati + validazione + righe)

**Tipo:** Feature backend
**Scope:** Backend
**PC:** `webmarke22`
**Priorità:** Alta
**Stima:** 3-4 ore
**Documento:** `docs/BE_FASTLDV_INTEGRATION.md`

**Contesto:**
**Unifica** `checkOrderData` + `validate.php` in **una sola chiamata** (miglioramento vs Smarty). Lookup `{code}`: `id_origin` PrestaShop oppure `id_order` se ordine gestionale (`id_origin=0`). Nessun prefisso `SM`.

**Response `200`** — ordine stampabile o avviso ristampa:
```json
{
  "status": "success",
  "data": {
    "id_origin": 69099,
    "id_order": 1234,
    "carrier": { "id_carrier_api": 5, "name": "BRT NAPOLI", "layout_type": "zebra" },
    "shipping": { "colli": 2, "peso": 1.5, "contrassegno": "0.00", "tracking": "", "country_iso": "IT" },
    "document": { "num_doc": "69099" },
    "lines": [{ "quantity": 2, "sku": "ABC123", "name": "Prodotto X" }],
    "validation": { "printable": true, "severity": "ok", "code": "OK", "message": "OK" }
  }
}
```

**Response `422`** — ordine trovato ma non stampabile: **stesso payload** + `validation.printable: false` + `validation.code` (es. `ORDER_NOT_PAID`). Miglioramento: UI ha righe e corriere senza seconda richiesta.

**Query:** `carrier`, `printer`, `id_store`, `skip_log`.

**Validazione:** regole da `validate.php`; ristampa → `severity: warning`, `code: LABEL_ALREADY_PRINTED` (non HTTP 202 separato).

**Opzionale:** blocco `data.legacy` con alias Smarty (`corrieri_*`, `id_doc`) per adapter PHP transitorio.

**Decisioni chiuse:** `id_origin` = PrestaShop. **Aperta:** auth `X-FastLDV-Key`; mapping `ready`/stati ordine.

**Pattern:** Router → `FastLdvOrderService` → Repository. Auth API key, no RBAC JWT.

---

### BE-FASTLDV-2 — `POST /api/v1/fastldv/notify-print`

**Tipo:** Feature backend
**Scope:** Backend
**PC:** `webmarke22`
**Priorità:** Alta
**Stima:** 1-2 ore
**Dipendenza:** BE-FASTLDV-1 (stessa autenticazione)
**Documento:** `docs/BE_FASTLDV_INTEGRATION.md`

**Contesto:**
**Nuovo** rispetto all'app attuale (oggi solo `log_stampa.php` locale + re-fetch Smarty). Scrive tracking sul gestionale dopo stampa etichetta.

**Request body:**
```json
{
  "id_origin": 69099,
  "tracking": "BRT123456789",
  "colli": 2,
  "carrier": "BRT NAPOLI",
  "operatore": "mario",
  "stampante": "ZDesigner ZT410"
}
```

**Comportamento:**
- `id_origin` → `orders.id_shipping` → `update_tracking` (**multispedizione accantonata v1**)
- Nessun cambio `id_order_state`
- `200 OK` fire-and-forget

**Modifica FastLDV (fase 2):** aggiungere POST in `logStampaAfterPrint()` (`app.js`) — adapter PHP.

---

### BE-FASTLDV-EVT — Emit + SSE tracking post-stampa (Angular real-time)

**Tipo:** Feature backend (+ coordinamento FE Angular)
**Scope:** Backend + FE gestionale
**PC:** `webmarke22` (BE), `webmarke26` (FE)
**Priorità:** Alta (dopo BE-FASTLDV-2)
**Stima:** ~1 giornata BE + 4–5 h FE
**Documento:** `docs/BE_FASTLDV_INTEGRATION.md` § BE-FASTLDV-EVT
**Origine:** nota FE `NOTA_BE_fastldv_tracking_events.md`

**Contesto:**
Dopo `notify-print` il tracking è in DB ma Angular richiede F5. Soluzione: `emit_event` su EventBus + `GET /api/v1/events/stream` (SSE, JWT). Evento `order.tracking.updated` con **`id_order`** (PK gestionale), non il codice PS del body notify.

**Decisioni chiuse:** SSE (no WebSocket, no polling, no epic N2); fan-out in-memory v1; emit non blocca notify-print.

**Acceptance:**
- [x] `ORDER_TRACKING_UPDATED` + emit in `notify_print` dopo commit
- [x] `GET /api/v1/events/stream` — SSE + auth JWT
- [x] Test: notify-print → client SSE riceve evento
- [x] (FE creative_light3) `OrderEventsService` + NgRx patch tracking
- [ ] QA congiunto BE+FE (checklist `docs/FE_HANDOFF_SSE_TRACKING.md`)

---

### BE-FASTLDV-3 — `PATCH /api/v1/fastldv/order/{code}/shipping-params`

**Tipo:** Feature backend
**Scope:** Backend
**PC:** `webmarke22`
**Priorità:** Media
**Stima:** 1-2 ore
**Dipendenza:** BE-FASTLDV-1
**Documento:** `docs/BE_FASTLDV_INTEGRATION.md`

**Contesto:**
Sostituisce `updateOrderData` — solo modalità **Verifica** in `app.js` (`eseguiVerifica`). Body: `colli`, `peso`, `contrassegno`, `rigenera` (0|1).

Necessario se si mantiene modifica colli (solo BRT NAPOLI in UI attuale) e rigenera spedizione.

---

**Acceptance criteria FastLDV (1 + 2):**
- [ ] GET unificato: dati spedizione + `lines` + `validation` in una response
- [ ] `200` se stampabile (ok o warning ristampa); `422` se bloccato con payload completo
- [ ] `validation.code` enum + messaggi IT da `validate.php`
- [ ] POST notify-print aggiorna `shipping.tracking`
- [ ] Auth `X-FastLDV-Key` implementata
- [ ] Test `FastLdvOrderService` + integration API

**Fuori scope iniziale:** `fastldvGetPdfPrint` / generazione ZPL — fase successiva verso API corrieri gestionale.

---

### ~~BE-VIES-ORDERS-AREA-C~~ — ✅ CHIUSO

**Tipo:** Feature backend (scope ridotto)
**Scope:** Backend
**PC:** `webmarke22`
**Priorità:** Alta
**Stima:** 1-2 ore

**Contesto:**
Dal recap BE: `apply-vies-exemption`, `bulk-apply-vies-exemption`, `bulk-vies-status` e il filtro `?vies_status=` sulla lista sono già implementati. Il filtro server-side rimane (non rimosso — era una decisione precedente da rivalutare ora che il BE lo ha già). Rimane da verificare/completare il toggle singolo.

**Scope residuo:**

1. **`PATCH /api/v1/orders/{id}/vies-status`** — verifica se già presente o da aggiungere
   ```http
   Body: { "vies_status": "eligible" | "not_eligible" | null, "vies_operator_note": string | null }
   Response: OrderDTO completo aggiornato
   ```
   Nota: distinto da `apply-vies-exemption` (che ricalcola le righe KO→OK). Questo è il toggle/revoca generico con ricalcolo IVA. Il FE usa `patchOrderViesStatus` in `orders.service.ts`.

2. **Smoke test** dei 3 endpoint già creati contro DB reale:
   - `PATCH apply-vies-exemption`
   - `POST bulk-apply-vies-exemption`
   - `GET /orders/?vies_status=eligible|not_eligible|null`

**Regola chiave FE (da `docs/FE_VIES_APPLY_EXEMPTION_BUTTON.md`):**
Usare sempre `PATCH apply-vies-exemption`, mai `PUT /orders/{id}` con solo `vies_status` (non ricalcola le righe).

**Acceptance criteria:**
- [ ] `PATCH /orders/{id}/vies-status` presente e funzionante
- [ ] `vies_status` esposto su `OrderDTO` (filtro client-side FE)
- [ ] Smoke test 3 endpoint su DB reale

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

Handler AS400 caso OK: sposta ordine a stato **3 (Spediti)**, non più a 2 (Pronti per la Spedizione).
Handler AS400 caso NOK: niente rollback, ordine resta in stato 2.

---

## 🟡 PRIORITÀ MEDIA — Da pianificare

### BE-ALIQ-03/04/06/07/08 — Completamento serie aliquote

**Tipo:** Feature / Debito tecnico
**Scope:** Backend
**PC:** `webmarke22`
**Priorità:** Media
**Programma:** `PROGRAMMA_BE_aliquote_vies.md` (sequenza: 08 → 03 → 04 → 07 → 05 → 06)

- **BE-ALIQ-03:** serializzazione corretta di `id_country` (nullable) nelle risposte Tax
- **BE-ALIQ-04:** invalidazione cache `/api/v1/init/` su modifica aliquote
- **BE-ALIQ-06:** seed aliquote per CI/testing
- **BE-ALIQ-07:** consolidamento API Tax (review endpoint, documentazione OpenAPI)
- **BE-ALIQ-08:** pulizia codice residuo multispedizione (`shipping_service.py:597`)

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

- Fix errore di collect: completare `user_client_async` fixture (manca `yield ac`)
- Aggiornare fixture RBAC: `admin_user` con `role_type='full_crud'`, `manager_user` con `role_type='custom'`
- Scrivere `test_permissions.py`: bypass full_crud, accesso negato permission_zero/module_not_found
- Valutare SQLite vs MySQL per i test

---

## 🔵 PRIORITÀ BASSA — Debito tecnico

### BE-TAX-DECIMAL — Completamento migrazione Numeric(5,2)

**Tipo:** Debito tecnico
**Scope:** Backend
**PC:** `webmarke22`

Il modello `Tax.percentage` è già `Numeric(5,2)` a livello di codice (fatto). Rimane da verificare che la colonna DB sia stata migrata e che tutti i consumatori (`order_repository`, `prestashop_service`, `fiscal_document`, `fatturapa`, `csv_import`, plugin AS400) gestiscano correttamente i decimali.

---

### BE-TAX-DEFINE-FIX — Riparazione `define_tax`

**Tipo:** Bug (non bloccante)
**Scope:** Backend
**PC:** `webmarke22`

`TaxRepository.define_tax(country_id)` ignora `country_id` e restituisce il primo `Tax` per `id_tax`. Valutare fix o sostituzione con `get_default_by_country`.

---

### BE-1 — Endpoint self-service profilo utente

**Tipo:** Feature
**Scope:** Backend
**PC:** `webmarke22`
**Stima:** 1-2 ore

- `PUT /users/me` — modifica nome, email, phone. Schema `UserSelfUpdate`.
- `PUT /users/me/password` — cambio password con verifica vecchia. Hash bcrypt.
- Auth: solo `Depends(get_current_user)`, no `require_permission`.

---

### BE-VIES-4 — FatturaPA N3.2 / art. 41 (Fase 4/4)

**Tipo:** Feature
**Scope:** Backend + FatturaPA
**PC:** `webmarke22`
**Priorità:** Da pianificare

Integrazione natura `N3.2` (art. 41 DL 331/93) nella generazione FatturaPA per ordini `vies_status = eligible`.

---

### BE-INFRA-ALEMBIC — Adozione Alembic come migration tool effettivo

**Tipo:** Infrastruttura
**Scope:** Backend
**PC:** `webmarke22`

`alembic/versions/` vuoto; schema gestito da `scripts/setup_initial.py`. Task indipendente da VIES.

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
- **ID API:** `id_origin` (PrestaShop); auth proposta `X-FastLDV-Key`
- **Task:** BE-FASTLDV-1 (GET unificato), 2 (notify-print), 3 opz. (shipping-params)
- **Prompt app magazzino:** `prompt_FE_fastldv_migration.md` (fase 2 adapter PHP)

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
- `BE-ALIQ-08` (bassa): rimuovere `update_order_status(request.id_order, 7)` da `shipping_service.py:597`
- Test VIES rapido: `pytest tests/unit/vies/ tests/unit/services/test_tax_service.py tests/unit/services/test_order_vies_exemption.py tests/unit/repository/test_order_create_vies_eligible_tax.py -v`

---

## 📝 Changelog

| Data | Evento |
|---|---|
| 2026-06-16 | BE-DDT-PRINT-PDF ✅ Fase 1–2: fix PDF DDT (`Decimal`/IVA/colli), test unit `test_ddt_pdf_service.py`. Handoff FE `docs/FE_HANDOFF_DDT_PRINT_PDF.md`. Aperto **FE-DDT-PRINT-PDF** |
| 2026-06-15 | BE-ORDER-PRINT-PDF ✅: `GET /orders/{id}/pdf`, `OrderPDFService`, handoff FE `docs/FE_HANDOFF_ORDER_PRINT_PDF.md`. Aperto FE-ORDER-PRINT-PDF (bottone stampa modale) |
| 2026-06-09 | BE-FASTLDV: endpoint unificato GET order (dati+validate+righe), `validation.code`, 422 con payload completo. Task 1/2/3. Doc + prompt aggiornati |
| 2026-06-09 | BE-FASTLDV: contratto iniziale da `app.js` + `validate.php`, `id_origin`. Doc `docs/BE_FASTLDV_INTEGRATION.md` |
| 2026-06-08 | FE-D.4 chiuso: bulk apply VIES dalla lista ordini su `POST /bulk-apply-vies-exemption` (contratto `{status,data:{processed,order_ids}}`). Apply singolo OK. Toggle PATCH vies-status non usato (D.3 in pausa). Verificato `vies_status` su tutti i DTO ordine (lista + by id) |
| 2026-06-08 | Aggiornamento con recap BE VIES/ALIQ: BE-ALIQ-00/02, BE-TAX-DECIMAL@modello, filtro vies_status lista, delete TAX_IN_USE marcati come chiusi |
| 2026-06-08 | Aggiunti BE-FASTLDV-1/2 (integrazione app magazzino) |
| 2026-06-08 | BE-VIES-ORDERS-AREA-C chiuso: toggle singolo vies_status eliminato dallo scope (flusso solo KO→OK, revoca non prevista) |
| 2026-06-08 | Creazione backlog unificato da fusione FE+BE |
