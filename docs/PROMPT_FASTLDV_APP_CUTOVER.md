# Prompt — Adattamento app FastLDV → ECommerceManagerAPI

**Uso:** copia tutto il contenuto sotto la riga `---` in una chat Cursor sul **repo FastLDV** (`proxy.php`, `assets/app.js`) quando si fa il cutover da Smarty.

**Prerequisito BE:** API deployate e testate su ambiente target.

| Endpoint | Stato |
|----------|--------|
| `GET /api/v1/fastldv/order/{code}` | ✅ |
| `POST /api/v1/fastldv/notify-print` | ✅ |
| `PATCH .../shipping-params` (Verifica) | ❌ opzionale, non ancora richiesto |

**Riferimento tecnico BE:** `ECommerceManagerAPI/docs/BE_FASTLDV_INTEGRATION.md` · Swagger tag **FastLDV**

**Nota:** l’aggiornamento real-time del gestionale Angular (SSE) è **già a posto lato BE+FE** — l’app magazzino non deve implementare nulla per quello; basta che `notify-print` funzioni.

---

## Contesto

L’app **FastLDV** oggi usa **GestionaleSmarty**:

- `checkOrderData` + `validate.php` (2 chiamate)
- Barcode con prefisso `SM` (es. `SM69099`)
- Dopo stampa: log locale + re-fetch Smarty per tracking

**Obiettivo cutover:** puntare al **gestionale ECommerceManagerAPI** mantenendo UI magazzino, BrowserPrint e le 3 modalità (Diretta / Verifica / Cerca).

---

## Cosa smettere di fare (Smarty)

| ❌ Legacy | ✅ Nuovo |
|----------|---------|
| Prefisso `SM` sul barcode | Solo **cifre intere** (`69100`, `457300`) |
| `checkOrderData` + `validate.php` | **1× GET** `/fastldv/order/{code}` |
| HTTP 202 per ristampa | `200` + `validation.code: LABEL_ALREADY_PRINTED` |
| Re-fetch Smarty post-stampa per tracking | **POST** `/fastldv/notify-print` |
| `validate.php` come file separato | Logica in `data.validation` della GET |

---

## Identificatori — regola fondamentale

Tre numeri diversi. **Non confonderli.**

| Nome | Significato | Esempio PS | Esempio gestionale |
|------|-------------|------------|-------------------|
| **`code`** (scansione) | Ciò che l’operatore digita/scansiona | `457300` | `69100` |
| **`id_origin`** (DB) | ID PrestaShop; **`0`** se ordine nato in app | `457300` | **`0`** |
| **`id_order`** (DB) | PK interna gestionale | `48564` | `69100` |

### Lookup automatico del BE

`GET /api/v1/fastldv/order/{code}`:

1. Cerca `orders.id_origin = {code}` → ordine PrestaShop  
2. Altrimenti `orders.id_order = {code}` se `id_origin` è `0` → ordine gestionale  

### Cosa usare nell’app

| Uso in app | Campo |
|------------|-------|
| Path GET `{code}` | Codice **scansionato** |
| Body notify `id_origin` | **Stesso codice scansionato** (nome legacy, non è sempre ID PS) |
| Header UI / footer ZPL | `data.document.num_doc` |
| Display documento | `data.document.num_doc` (non `data.id_origin` se gestionale: sarebbe `0`) |

**⚠️ Errore da evitare:** per ordini gestionale, `data.id_origin` in risposta GET è **`0`**. Il notify-print deve inviare il **codice scansionato** (`69100`), non `data.id_origin`.

Conservare in memoria per tutta la sessione ordine:

```javascript
let lastScannedCode = null;  // impostato alla scansione, usato in notify-print
```

---

## Configurazione (`.env` PHP — server only)

```env
GESTIONALE_API_BASE=http://<host-api>:8000
FASTLDV_API_KEY=<chiave-senza-spazi>
USE_GESTIONALE_API=true
```

- `FASTLDV_API_KEY` **mai** in `app.js` client — solo `proxy.php`
- `USE_GESTIONALE_API=false` → rollback verso Smarty (mantenere branch legacy)

---

## Autenticazione API

```http
X-FastLDV-Key: <FASTLDV_API_KEY>
```

Nessun JWT. Sessione PHP magazziniere (`$_SESSION`) resta invariata lato app.

---

## API 1 — GET ordine unificato

Sostituisce `checkOrderData` + `validate.php`.

```http
GET {GESTIONALE_API_BASE}/api/v1/fastldv/order/{code}?carrier=BRT+NAPOLI&printer=ZDesigner+ZT410
X-FastLDV-Key: ...
```

| Query | Note |
|-------|------|
| `carrier` | Consigliato (safety-net vs corriere ordine) |
| `printer` | Opzionale, audit log |
| `id_store` | Solo multi-negozio |
| `skip_log` | `1` = anteprima senza log |

### Gestione HTTP

| HTTP | Condizione | Azione UI |
|------|------------|-----------|
| `200` | `validation.printable: true` | Procedi stampa (`ok` o `warning` ristampa) |
| `422` | `validation.printable: false` | Mostra `validation.message` + **tabella righe** (payload completo) |
| `404` | Ordine non trovato | Messaggio come oggi |
| `400` | `CARRIER_NOT_ASSIGNED` | "Corriere non assegnato" |
| `401` | Key errata | Errore configurazione |

### `validation.code` (enum)

| Code | Stampabile | Significato |
|------|------------|-------------|
| `OK` | sì | Ordine pronto |
| `LABEL_ALREADY_PRINTED` | sì (warning) | Ristampa — modale countdown come oggi |
| `BYPASS` | sì | Whitelist env `FASTLDV_BYPASS_VALIDATE_IDS` |
| `ORDER_CANCELED` | no | Annullato |
| `ORDER_LOCKED` | no | Bloccato |
| `ORDER_NOT_PAID` | no | Non pagato |
| `ORDER_ALREADY_SHIPPED` | no | Già spedito |
| `ORDER_NOT_READY` | no | Non in lavorazione |

### Esempio risposta — ordine gestionale

```json
{
  "status": "success",
  "data": {
    "id_origin": 0,
    "id_order": 69100,
    "carrier": { "id_carrier_api": 6, "name": "BRT NAPOLI", "layout_type": "zebra" },
    "shipping": { "colli": 1, "peso": 26.45, "contrassegno": "0.00", "tracking": "", "country_iso": "IT" },
    "document": { "num_doc": "69100" },
    "lines": [{ "quantity": 1, "sku": "SKU-1", "name": "Prodotto X" }],
    "validation": { "printable": true, "severity": "ok", "code": "OK", "message": "OK" }
  }
}
```

### Mapping verso oggetto UI (adapter)

```javascript
function mapOrderContext(data) {
  return {
    order: {
      id_order: data.id_order,
      id_carrier: data.carrier.id_carrier_api,
      carrier: data.carrier.name,
      colli: data.shipping.colli,
      peso: data.shipping.peso,
      contrassegno: data.shipping.contrassegno,
      tracking: data.shipping.tracking || '',
      layout_type: data.carrier.layout_type,
      num_doc: data.document.num_doc,   // footer ZPL / header
    },
    lines: data.lines,                  // quantity è numero intero
    validation: data.validation,
    country_iso: data.shipping.country_iso,
  };
}
```

Opzionale transizione: se presente `data.legacy`, alias Smarty (`corrieri_*`, `id_doc`) per adapter graduale.

---

## API 2 — POST notify-print

Dopo stampa etichetta **OK** e tracking/AWB noto.

```http
POST {GESTIONALE_API_BASE}/api/v1/fastldv/notify-print
Content-Type: application/json
X-FastLDV-Key: ...
```

```json
{
  "id_origin": 69100,
  "tracking": "BRT123456789",
  "colli": 2,
  "carrier": "BRT NAPOLI",
  "operatore": "mario",
  "stampante": "ZDesigner ZT410"
}
```

| Campo body | Valore |
|------------|--------|
| `id_origin` | **`lastScannedCode`** (codice path GET), non `data.id_origin` dalla risposta |
| `tracking` | AWB/tracking restituito da stampa corriere |

**Comportamento BE:** aggiorna `shipping.tracking`; **non** cambia stato ordine; emette evento SSE verso gestionale Angular (trasparente per l’app).

**App:** fire-and-forget — non bloccare l’operatore se fallisce:

```javascript
fetch('proxy.php?action=notifyPrint', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    id_origin: lastScannedCode,
    tracking: awb,
    colli: lastOrderContext.order.colli,
    carrier: lastOrderContext.order.carrier,
    operatore: sessionOperatore,
    stampante: printerName,
  }),
}).catch(() => {});
```

Risposta `200` esempio:

```json
{
  "status": "success",
  "data": {
    "id_origin": 0,
    "id_order": 69100,
    "id_shipping": 123,
    "tracking": "BRT123456789",
    "awb": "BRT123456789"
  }
}
```

---

## Modifiche `proxy.php`

Nuove action (oltre al fallback Smarty se `USE_GESTIONALE_API=false`):

| Action | Metodo | Backend |
|--------|--------|---------|
| `orderContext` | GET | `/api/v1/fastldv/order/{code}` |
| `notifyPrint` | POST | `/api/v1/fastldv/notify-print` |

Propagare **status HTTP e body JSON** al client (incluso `422` con payload completo).

```php
// orderContext — esempio
$code = (int)($_GET['code'] ?? 0);
$url = GESTIONALE_API_BASE . "/api/v1/fastldv/order/{$code}";
// curl + header X-FastLDV-Key: FASTLDV_API_KEY
// http_response_code($status); echo $body;
```

---

## Modifiche `app.js` — checklist

### Scansione

```javascript
// PRIMA
// const code = 'SM' + digits;

// DOPO
const code = parseInt(scannedValue, 10);
if (!Number.isFinite(code) || code <= 0) { /* errore */ }
lastScannedCode = code;
const res = await fetchOrderContext(code);
```

### Validazione (sostituisce validate.php)

```javascript
const ctx = mapOrderContext(res.data);
renderOrderLines(ctx.lines);

if (!ctx.validation.printable) {
  setStatus(ctx.validation.message, 'error');
  return;
}
if (ctx.validation.severity === 'warning') {
  await showReprintConfirm(ctx.validation.message);
}
// procedi stampa...
```

### Tre modalità

| Modalità | Flusso nuovo |
|----------|--------------|
| **Diretta** | GET → stampa → notify-print |
| **Cerca** | GET (solo lettura) |
| **Verifica** | GET → (opz. PATCH params **se BE-FASTLDV-3 deployato**) → stampa → notify-print |

### UI / etichette

| Elemento | Prima | Dopo |
|----------|-------|------|
| Barcode | `SM` + cifre | Solo cifre |
| Header ordine | `SM{id}` | `num_doc` |
| Footer ZPL | `SM{digits}` | `data.document.num_doc` |
| Titolo corriere | `SM{id} · carrier` | `{num_doc} · {carrier}` |

---

## Fuori scope v1 (non implementare ora)

| Tema | Nota |
|------|------|
| **Multispedizione** | BE usa solo `orders.id_shipping` principale |
| **SSE / gestionale Angular** | Già fatto — solo notify-print |
| **Generazione ZPL/PDF** (`fastldvGetPdfPrint`) | Resta Smarty o corriere fino a Fase 4 |
| **PATCH shipping-params** | Solo se serve modalità Verifica (BE-FASTLDV-3) |
| **Prefisso `SM`** | Non reintrodurre |

---

## Test plan cutover

| # | Scenario | Esito atteso |
|---|----------|--------------|
| 1 | Ordine gestionale `id_order=69100`, scan `69100` | GET `200` o `422` con righe; `id_origin: 0` in risposta |
| 2 | Ordine PS, scan `id_origin` PS | GET ok; `num_doc` = ID PS |
| 3 | Ordine non pagato | `422`, messaggio IT, righe visibili |
| 4 | Ristampa con tracking | `200`, `LABEL_ALREADY_PRINTED`, modale warning |
| 5 | Stampa OK | notify-print → tracking in DB gestionale |
| 6 | Gestionale Angular su `/orders` | Tracking visibile senza F5 (QA con team FE) |
| 7 | `USE_GESTIONALE_API=false` | Rollback Smarty funzionante |

### Curl smoke test (senza app)

```bash
# GET ordine gestionale
curl -s -H "X-FastLDV-Key: $FASTLDV_API_KEY" \
  "http://localhost:8000/api/v1/fastldv/order/69100?carrier=BRT+NAPOLI"

# Notify-print
curl -s -X POST -H "Content-Type: application/json" -H "X-FastLDV-Key: $FASTLDV_API_KEY" \
  -d '{"id_origin":69100,"tracking":"BRT-TEST-001","colli":1,"carrier":"BRT","operatore":"test","stampante":"ZDesigner"}' \
  "http://localhost:8000/api/v1/fastldv/notify-print"
```

---

## Stima effort app

| Task | Ore |
|------|-----|
| `proxy.php` (2 action + rollback) | 2–3 |
| `app.js` refactor fetch + validazione | 3–4 |
| notify-print + UI `SM` removal | 1–2 |
| Test magazzino 3 modalità | 2–4 |
| **Totale** | **1–2 giornate** |

---

## Vincoli finali

- API key **solo server-side** PHP
- Notify-print **non blocca** l’operatore
- Messaggi utente in **italiano**
- Conservare BrowserPrint, Gel Proximity, Fermo Point come oggi
- In caso di dubbio su identificatori: **notify usa `lastScannedCode`**, etichetta usa **`document.num_doc`**
