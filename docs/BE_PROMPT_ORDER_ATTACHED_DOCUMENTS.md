# Prompt BE — Documenti annessi all’ordine (pattern API unico)

## Contesto
Nel dettaglio ordine (tab **Resi / Fatture / Ricevute**) il frontend Angular carica i documenti collegati all’ordine con **tre GET** che oggi hanno **path, envelope e semantica “vuoto” diversi**.

Questo rende fragile il FE (workaround su 404 fatture) e rende incoerente il contratto OpenAPI.

### Chiamate attuali (as-is)

| Dominio | Endpoint attuale | Empty state oggi |
|--------|-------------------|------------------|
| Resi | `GET /api/v1/orders/{id_order}/returns` | `200` + lista (tipicamente `{ "returns": [] }`) |
| Ricevute | `GET /api/v1/ricevute/?id_order={id_order}&page=1&limit=50` | `200` + lista paginata |
| Fatture | `GET /api/v1/fiscal_documents/invoices/order/{id_order}` | spesso **`404`** se nessuna fattura → FE lo mappa a `[]` |

Esempi reali osservati in Network (ordine `69141`):

```http
GET /api/v1/orders/69141/returns
GET /api/v1/ricevute/?id_order=69141&page=1&limit=50
GET /api/v1/fiscal_documents/invoices/order/69141   → 404 Not Found
```

---

## Obiettivo richiesto
Unificare il **list-by-order** dei tre domini sotto un **unico pattern nested sull’ordine**, allineato ai resi (già corretti).

Non è richiesto in questo task un endpoint aggregate unico (`attached-documents`): bastano **tre collection** con lo **stesso shape di path + stessa semantica HTTP + stesso envelope**.

---

## Contratto target (to-be)

### Path (pattern unico)

```http
GET /api/v1/orders/{id_order}/returns
GET /api/v1/orders/{id_order}/invoices
GET /api/v1/orders/{id_order}/ricevute
```

Regole path:

1. Sempre prefisso `/api/v1/orders/{id_order}/…`
2. Collection al plurale (`returns`, `invoices`, `ricevute`)
3. Nessun query `id_order` obbligatorio per questi endpoint (l’ordine è nel path)
4. Paginazione opzionale uniforme se serve: `?page=1&limit=50` (default ragionevoli documentati)

### Semantica HTTP (obbligatoria)

| Situazione | Status | Body |
|-----------|--------|------|
| Ordine esistente, 0 documenti | **`200`** | envelope con `items: []`, `total: 0` |
| Ordine esistente, N documenti | **`200`** | envelope con items popolati |
| Ordine inesistente | **`404`** | errore standard |
| Non autorizzato | **`401` / `403`** | errore standard |

**Vietato** rispondere `404` per “nessun documento collegato”.  
Il `404` deve significare solo “ordine non trovato” (o risorsa padre assente).

### Envelope comune (obbligatorio)

```json
{
  "items": [],
  "total": 0
}
```

Campi:

- `items`: array di oggetti del dominio (resi / fatture / ricevute)
- `total`: numero totale elementi (anche senza paginazione: `total === items.length`)

Paginazione opzionale (se implementata):

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "limit": 50
}
```

### Compatibilità envelope legacy (transizione)

Per una release di transizione è accettabile esporre **anche** la chiave storica oltre a `items`:

| Endpoint | Alias opzionale in transizione |
|---------|--------------------------------|
| `/returns` | `returns` (già usato) |
| `/invoices` | `invoices` |
| `/ricevute` | `ricevute` |

Target stabile: solo `items` + `total`. Gli alias vanno marcati deprecated in OpenAPI.

---

## Contenuto minimo degli `items` (lista tab ordine)

Payload lista **sintetico** sufficiente alla UI tab (non serve il dettaglio completo).

### Resi — `GET .../returns`
Campi minimi già usati FE (mantenere compatibilità con schema reso attuale):

```json
{
  "items": [
    {
      "id_fiscal_document": 10,
      "id_order": 69141,
      "document_number": "R-2026-01",
      "date_add": "2026-08-06T10:00:00",
      "status": "…"
    }
  ],
  "total": 1
}
```

### Fatture — `GET .../invoices`
Allineare ai campi lista/dettaglio fattura già usati dal FE (`InvoiceDetail` / documento fiscale), almeno:

```json
{
  "items": [
    {
      "id": 55,
      "id_order": 69141,
      "numero_documento": "A-2026-445",
      "tipo_documento": "invoice",
      "date_add": "2026-08-06",
      "total_price_with_tax": 1853.70,
      "is_payed": true,
      "stato": "emessa"
    }
  ],
  "total": 1
}
```

Note:

- Un ordine può avere **più** fatture → sempre array.
- Se oggi `/fiscal_documents/invoices/order/{id}` restituisce array “nudo”, il nuovo endpoint deve usare l’envelope `{ items, total }`.
- I campi quick-status (`mail_status`, `fatturapa_status`, ecc.) restano quelli del contratto stato rapido se già presenti sul documento.

### Ricevute — `GET .../ricevute`
Campi minimi allineati a `RicevutaListItem`:

```json
{
  "items": [
    {
      "id_ricevuta": 12,
      "id_order": 69141,
      "numero": "RIC-2026-01",
      "stato": "emessa",
      "data_emissione": "2026-08-06",
      "totale": 100.00
    }
  ],
  "total": 1
}
```

---

## Endpoint legacy (deprecare, non rimuovere subito)

Mantenere in parallelo per almeno una release, poi deprecare in OpenAPI:

| Legacy | Sostituito da |
|--------|----------------|
| `GET /api/v1/fiscal_documents/invoices/order/{id_order}` | `GET /api/v1/orders/{id_order}/invoices` |
| Uso di `GET /api/v1/ricevute/?id_order=…` come **unico** modo per “ricevute dell’ordine” | `GET /api/v1/orders/{id_order}/ricevute` |

Restano validi (fuori scope di questo prompt):

- `GET /api/v1/ricevute/` — lista globale pagina Ricevute
- `GET /api/v1/fiscal_documents/` — lista globale documenti fiscali
- CRUD/dettaglio by-id esistenti

Durante la transizione, i legacy devono rispettare la stessa regola empty:

- preferibile allineare anche il legacy fatture a **`200` + `[]`** (invece di 404), così il FE può rimuovere il workaround anche prima del cut-over completo.

---

## Fuori scope

- Unificare create/update/delete dei tre domini
- Endpoint aggregate `GET /orders/{id}/attached-documents`
- Cambiare i flussi di emissione fattura/ricevuta/reso
- Note di credito (eventuale estensione futura: `GET /orders/{id}/credit-notes`)

---

## Attività BE richieste

1. Implementare (o allineare) i tre GET nested sotto `/api/v1/orders/{id_order}/…`.
2. Uniformare envelope `{ items, total }` (+ paginazione opzionale).
3. Garantire **200 + lista vuota** quando non ci sono documenti; **404 solo se ordine assente**.
4. Aggiornare OpenAPI / schema response.
5. Mantenere legacy con header/doc di deprecation.
6. Test:
   - ordine senza documenti → 200 + `items: []` su tutti e tre
   - ordine con documenti misti → liste corrette e filtrate per `id_order`
   - ordine inesistente → 404
   - regressione: create reso / emit fattura / emit ricevuta ancora ok

---

## Impatto FE (dopo rilascio BE — task separato)

Quando i nuovi endpoint sono disponibili:

1. Aggiornare path in:
   - `OrdersService.getReturnsByOrder` (già ok o solo envelope)
   - `FiscalDocumentsService.getInvoicesByOrder` → `/orders/{id}/invoices`
   - load ricevute tab ordine → `/orders/{id}/ricevute` (oggi HTTP diretto nel modal)
2. Rimuovere workaround `404 → []` su invoices-by-order (`FiscalDocumentsService` + nota in `ErrorInterceptor`).
3. Normalizzare parsing envelope su `items` (con fallback temporaneo alle chiavi legacy).
4. Allineare ricevute tab a NgRx come resi/fatture (debito attuale: chiamata service nel modal).

---

## Done criteria

- Esistono i tre endpoint nested con path coerente.
- Empty state sempre `200` + `items: []` (mai 404 “nessun documento”).
- Envelope comune documentato in OpenAPI.
- Legacy ancora funzionanti ma marcati deprecated.
- FE può migrare senza euristiche sul 404 fatture.
