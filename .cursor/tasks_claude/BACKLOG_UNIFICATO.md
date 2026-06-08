# Backlog Unificato — Elettronew Gestionale e-commerce

> Generato il 2026-06-08 dalla fusione di `BACKLOG.md` (PC FE `webmarke26`) e `BACKLOG.md` (PC BE `webmarke22`).
> Aggiornato 2026-06-08 con recap implementazione VIES/ALIQ dal BE.
> Fonte di verità consolidata per proseguire il lavoro su entrambi i PC.

---

## 📊 Sommario stato (riconciliato)

| Area | ✅ Done | 🟦 Backlog aperto | 🌟 Epic |
|---|---|---|---|
| **Backend** | 35+ (..., BE-VIES-ORDERS-AREA-C ✅) | 6 (BE-FASTLDV-1/2, BE-VIES-4, BE-ALIQ-03..08, BE-1, BE-TAX-DEFINE-FIX, BE-INFRA-ALEMBIC, REPLAN-AS400-PR7) | — |
| **Frontend** | 20+ (vedi storico) | 9 (FE-4, FE-1, FE-5, FE-6, FE-8, FE-10, FE-13, FE-REFACT, T1) | 2 (N1, N2) |

---

## 🔴 PRIORITÀ ALTA — Da fare subito

### BE-FASTLDV-1 — `GET /api/v1/fastldv/order/{id}`

**Tipo:** Feature backend
**Scope:** Backend
**PC:** `webmarke22`
**Priorità:** Alta
**Stima:** 2-3 ore
**Dipendenza:** allineamento con chi gestisce FastLDV su quale `{id}` viene scansionato (id_order interno o id_ecommerce PrestaShop)

**Contesto:**
FastLDV custom sostituirà le chiamate verso GestionaleSmarty (`validate.php` + `checkOrderData`) con questo endpoint. Restituisce i dati necessari per validazione e pannello articoli.

**Response:**
```json
{
  "id_order": 123,
  "carrier": "BRT",
  "id_carrier_api": 5,
  "colli": 2,
  "peso": 1.5,
  "contrassegno": "0.00",
  "tracking": "",
  "paid": true,
  "locked": false,
  "canceled": false,
  "shipped": false,
  "shipping_confirmed": false,
  "lines": [
    { "quantity": "2", "sku": "ABC123", "name": "Prodotto X" }
  ]
}
```

**Flag di validazione** (logica identica a `validate.php` Smarty):
- `canceled: true` → blocca
- `locked: true` → blocca
- `paid: false` → blocca
- `shipped: false` → blocca
- `shipping_confirmed: true` → blocca
- `tracking` non vuoto → avviso ristampa (non bloccante)

**Decisioni aperte prima dell'implementazione:**
- Quale `{id}` scansiona il magazziniere? `id_order` interno o `id_ecommerce` PrestaShop?
- Autenticazione: API key statica in header (`X-FastLDV-Key`) o rete locale trusted?

**Pattern architetturale:** Router → Service → Repository → Model (standard progetto)
**RBAC:** valutare bypass con API key dedicata invece del sistema operatori

---

### BE-FASTLDV-2 — `POST /api/v1/fastldv/notify-print`

**Tipo:** Feature backend
**Scope:** Backend
**PC:** `webmarke22`
**Priorità:** Alta
**Stima:** 1-2 ore
**Dipendenza:** BE-FASTLDV-1 (stessa autenticazione)

**Contesto:**
Chiamato da FastLDV dopo ogni stampa etichetta riuscita. Aggiorna `shipping.tracking` sull'ordine.

**Request body:**
```json
{
  "id_order": 123,
  "tracking": "BRT123456789",
  "colli": 2,
  "carrier": "BRT",
  "operatore": "mario",
  "stampante": "ZDesigner ZT410"
}
```

**Comportamento:**
- Aggiorna `shipping.tracking` (e `shipping.awb` se applicabile)
- Risposta `200 OK` — FastLDV non blocca sulla risposta
- Nessun cambio stato ordine (solo tracking, per decisione di prodotto)

**Acceptance criteria:**
- [ ] GET restituisce struttura attesa con flag validazione corretti
- [ ] POST aggiorna `shipping.tracking`
- [ ] Autenticazione definita e implementata
- [ ] Test per entrambi gli endpoint

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
| 2026-06-08 | Aggiornamento con recap BE VIES/ALIQ: BE-ALIQ-00/02, BE-TAX-DECIMAL@modello, filtro vies_status lista, delete TAX_IN_USE marcati come chiusi |
| 2026-06-08 | Aggiunti BE-FASTLDV-1/2 (integrazione app magazzino) |
| 2026-06-08 | BE-VIES-ORDERS-AREA-C chiuso: toggle singolo vies_status eliminato dallo scope (flusso solo KO→OK, revoca non prevista) |
| 2026-06-08 | Creazione backlog unificato da fusione FE+BE |
