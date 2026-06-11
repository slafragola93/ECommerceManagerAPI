# Prompt sessione FE — Migrazione FastLDV → ECommerceManagerAPI

Copia tutto il contenuto sotto la riga `---` e incollalo in una nuova chat Cursor/Claude sul **progetto FastLDV** (`fastldv/` — `assets/app.js`, `proxy.php`).

**Prerequisito:** BE deployato con `GET /api/v1/fastldv/order/{code}` + `POST /api/v1/fastldv/notify-print` testati. Contratto: `docs/BE_FASTLDV_INTEGRATION.md` nel repo ECommerceManagerAPI.

---

## Contesto

L’app **FastLDV** oggi usa **GestionaleSmarty** (`checkOrderData`, `validate.php`, prefisso barcode `SM…`).  
**La nuova app sostituisce Smarty** e parla con **ECommerceManagerAPI**.

### Cosa NON fare più (legacy Smarty)

- ❌ Prefisso `SM` sul barcode (`SM69099`)
- ❌ Due chiamate `checkOrderData` + `validate.php`
- ❌ Costruire `code=SM{digits}` nel proxy
- ❌ Usare `id_doc` Smarty come chiave API

### Cosa fare (nuovo stack)

- ✅ Scansione → **solo cifre intere** (es. `69100`)
- ✅ **Una GET** `GET /api/v1/fastldv/order/{code}`
- ✅ Il **backend risolve** PrestaShop vs ordine gestionale (vedi sotto)
- ✅ Dopo stampa OK → `POST /api/v1/fastldv/notify-print`

---

## Identificatore ordine — regola fondamentale

Il path `{code}` è il **numero scansionato** (intero). Il BE fa lookup automatico:

| Tipo ordine | DB | Cosa passi in `{code}` | Esempio |
|-------------|-----|------------------------|---------|
| PrestaShop (sync) | `id_origin = 457300` | `457300` | `GET .../order/457300` |
| Gestionale (creato in app) | `id_origin = 0` | **`id_order`** | `GET .../order/69100` |

**In risposta:**

- `data.id_origin` = valore **reale** `orders.id_origin` (ID PS oppure **`0`** se gestionale — non sostituito con `id_order`)
- `data.id_order` = PK interna gestionale (sempre presente)
- `data.document.num_doc` = codice etichetta (PS id se sync, altrimenti `id_order`)

Per ordini gestionale: barcode `{code}` = `id_order`, ma `data.id_origin` resta **`0`**.

---

## Obiettivo task FE (fase 1)

1. **Config** — `GESTIONALE_API_BASE`, `FASTLDV_API_KEY` in `.env` PHP (key **solo server-side**).
2. **`proxy.php`** — nuova action `orderContext` → proxy verso gestionale (1 GET).
3. **`app.js`** — `fetchOrderContext(code)` sostituisce `fetchOrderData` + `validateOrder`.
4. **`logStampaAfterPrint`** — aggiungere `POST notify-print` (fire-and-forget).
5. **Flag** `USE_GESTIONALE_API=true|false` per rollback Smarty.
6. **Invariato fase 1:** BrowserPrint, 3 modalità, `fastldvGetPdfPrint` (ZPL ancora Smarty se serve).

**Fuori scope v1:** multispedizione; `PATCH shipping-params` (solo se modalità Verifica e BE-FASTLDV-3 deployato).

---

## API Backend

### Auth

```http
X-FastLDV-Key: <FASTLDV_API_KEY>
```

Solo da PHP proxy, mai esporre la key in JS client.

### 1) GET ordine unificato (sostituisce checkOrderData + validate)

```http
GET {GESTIONALE_API_BASE}/api/v1/fastldv/order/{code}?carrier=BRT+NAPOLI&printer=ZDesigner+ZT410
X-FastLDV-Key: ...
```

| HTTP | Quando | Azione UI |
|------|--------|-----------|
| `200` | `validation.printable: true` | Procedi stampa (ok o warning ristampa) |
| `422` | `validation.printable: false` | Mostra `validation.message` + **tabella righe** (payload completo) |
| `404` | ordine non trovato | Messaggio come oggi |
| `400` | `CARRIER_NOT_ASSIGNED` | "Corriere non assegnato" |
| `401` | key errata | Errore config |

**Esempio 200 OK (ordine gestionale `id_order=69100`, `id_origin` DB = 0):**

```json
{
  "status": "success",
  "data": {
    "id_origin": 0,
    "id_order": 69100,
    "carrier": { "id_carrier_api": 6, "name": "BRT", "layout_type": "pdf" },
    "shipping": { "colli": 1, "peso": 26.45, "contrassegno": "0.00", "tracking": "", "country_iso": "FR" },
    "document": { "num_doc": "69100" },
    "lines": [{ "quantity": 1, "sku": "NCO ...", "name": "..." }],
    "validation": { "printable": true, "severity": "ok", "code": "OK", "message": "OK" }
  }
}
```

**Warning ristampa** (`200`, `validation.code === "LABEL_ALREADY_PRINTED"`, `severity: "warning"`): mostra modale avviso, stampa consentita.

**422 esempio** (`ORDER_NOT_READY`, `ORDER_NOT_PAID`, ecc.): leggi `data.validation.message`, renderizza comunque `data.lines`.

### 2) POST notify-print (dopo stampa OK)

```http
POST {GESTIONALE_API_BASE}/api/v1/fastldv/notify-print
Content-Type: application/json
X-FastLDV-Key: ...

{
  "id_origin": 69100,
  "tracking": "BRT123456789",
  "colli": 2,
  "carrier": "BRT",
  "operatore": "mario",
  "stampante": "ZDesigner ZT410"
}
```

> Il campo JSON `id_origin` nel body = **`code` scansionato** (ID PS o `id_order` se gestionale). Non è `data.id_origin` dalla GET (che per gestionale è `0`).

Fire-and-forget: `.catch(() => {})` — non bloccare l’operatore.

---

## Implementazione `app.js`

### Rimuovere logica Smarty sulla scansione

```javascript
// PRIMA (Smarty) — RIMUOVERE
// const code = 'SM' + digits;
// fetch('proxy.php?action=checkOrderData&code=' + code);

// DOPO (gestionale)
const code = parseInt(scannedValue, 10);  // solo cifre, MIN_DIGITS come oggi
if (!Number.isFinite(code) || code <= 0) { /* errore */ }

const res = await fetchOrderContext(code);
```

### Nuova `fetchOrderContext(code)`

Chiama `proxy.php?action=orderContext&code={code}` (PHP aggiunge `X-FastLDV-Key`).

Mappa risposta BE → oggetto usato dall’UI esistente:

```javascript
function mapOrderContext(data) {
  const docId = data.id_origin;  // già normalizzato dal BE
  return {
    order: {
      id_doc: docId,
      id_order: data.id_order,
      id_carrier: data.carrier.id_carrier_api,
      carrier: data.carrier.name,
      colli: data.shipping.colli,
      peso: data.shipping.peso,
      contrassegno: data.shipping.contrassegno,
      tracking: data.shipping.tracking || '',
      layout_type: data.carrier.layout_type,
      num_doc: data.document.num_doc,
    },
    lines: data.lines,
    validation: data.validation,
    country_iso: data.shipping.country_iso,
  };
}
```

### Logica UI (sostituisce validate.php)

```javascript
const ctx = await fetchOrderContext(code);
renderOrderLines(ctx.lines);

if (!ctx.order.carrier) {
  setStatus('Corriere non assegnato', 'error');
  return;
}
if (!ctx.validation.printable) {
  setStatus(ctx.validation.message, 'error');
  return;  // 422: righe già renderizzate
}
if (ctx.validation.severity === 'warning') {
  await showReprintConfirm(ctx.validation.message);
}
// procedi stampa...
```

### `logStampaAfterPrint`

Dopo stampa OK e tracking noto:

```javascript
fetch('proxy.php?action=notifyPrint', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    id_origin: lastOrderContext.order.id_doc,  // data.id_origin dalla GET
    tracking: awb,
    colli: lastOrderContext.order.colli,
    carrier: lastOrderContext.order.carrier,
    operatore: sessionOperatore,
    stampante: printerName,
  }),
}).catch(() => {});
```

---

## Implementazione `proxy.php`

```env
GESTIONALE_API_BASE=http://192.168.130.119:8000
FASTLDV_API_KEY=...
USE_GESTIONALE_API=true
```

**`action=orderContext`:**

```php
$code = (int)($_GET['code'] ?? 0);
$url = GESTIONALE_API_BASE . "/api/v1/fastldv/order/{$code}";
// curl con header X-FastLDV-Key
// Propaga status 200/422/404 e body JSON al client
```

**`action=notifyPrint`:** POST verso `/api/v1/fastldv/notify-print` con stesso header.

Se `USE_GESTIONALE_API=false` → fallback legacy Smarty (rollback).

---

## UI da aggiornare (ex Smarty)

| Elemento | Prima (Smarty) | Dopo |
|----------|----------------|------|
| Barcode / input | `SM` + cifre | **solo cifre** |
| Header ordine | `SM{id}` | `{data.id_origin}` o `{data.document.num_doc}` |
| Footer ZPL | `SM{digits}` | `{data.id_origin}` (senza prefisso) |
| Display corriere | `SM{id} · carrier` | `{data.id_origin} · {carrier.name}` |
| ID per notify | id_doc Smarty | `data.id_origin` dalla GET |

---

## Checklist file

- [ ] `.env` — `GESTIONALE_API_BASE`, `FASTLDV_API_KEY`, `USE_GESTIONALE_API`
- [ ] `proxy.php` — `orderContext`, `notifyPrint`
- [ ] `app.js` — rimuovi `SM`, `fetchOrderContext`, aggiorna 3 modalità
- [ ] `logStampaAfterPrint` — notify-print
- [ ] Rimuovi/depreca chiamate dirette a `validate.php` Smarty
- [ ] **Non toccare fase 1:** `fastldvGetPdfPrint`, BrowserPrint, Gel Proximity

---

## Test plan

1. **Ordine gestionale** (`id_origin=0`, es. `id_order=69100`) — GET con `code=69100` → 200 o 422 con righe.
2. **Ordine PrestaShop** — GET con `code={id_origin PS}`.
3. **Cerca** — 1 GET, messaggio blocco da `validation`.
4. **Diretta** — stampa → notify-print → tracking in DB.
5. **Ristampa** — `LABEL_ALREADY_PRINTED` + modale warning.
6. **Rollback** — `USE_GESTIONALE_API=false` → Smarty.

---

## Riferimenti BE

- `ECommerceManagerAPI/docs/BE_FASTLDV_INTEGRATION.md`
- Swagger: `{GESTIONALE_API_BASE}/docs` → tag **FastLDV**
- Test curl: `GET /api/v1/fastldv/order/69100` con header `X-FastLDV-Key`

---

## Vincoli

- Tre modalità (diretta / verifica / cerca) devono restare funzionanti.
- Messaggi utente in italiano.
- API key solo server-side PHP.
- Notify-print non blocca l’operatore se fallisce.
