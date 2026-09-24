# Prompt BE — Create fattura parziale (schema come NC)

Incolla questo messaggio nella chat sul **repo ECommerceManagerAPI**.

---

## Contesto

Il FE emette fatture parziali da dettaglio ordine (modale selezione righe/qty). Oggi:

```http
POST /api/v1/fiscal_documents/invoices
```

`InvoiceCreateSchema` accetta **solo** `id_order`. Extra (`items`, `is_partial`, `order_line_items`) vengono ignorati → snapshot **intero ordine** → importo pieno e rischio di rifatturare le stesse qty se si prova a “limare” dopo con PATCH.

Le **note di credito** hanno già il contratto atomico:

```json
POST /api/v1/fiscal_documents/credit-notes
{
  "id_invoice": 62,
  "reason": "...",
  "is_partial": true,
  "include_shipping": false,
  "items": [{ "id_order_detail": 456, "quantity": 2 }]
}
```

`is_partial: true` senza `items` → **422**. Snapshot = solo quelle righe. Una transazione.

Il **DDT parziale** è lo stesso pattern (`articoli: [{ id_order_detail, quantity }]`).

**Obiettivo:** allineare `InvoiceCreateSchema` / `POST /invoices` allo stesso modello. **Niente endpoint nuovo.** Niente PATCH di follow-up per simulare la parziale.

---

## Contratto `POST /api/v1/fiscal_documents/invoices`

Path, auth e permesso invariati (`fiscal_documents.create`). Response 201 = stesso shape v3 del GET dettaglio (`order_details` = **snapshot fiscale**, non righe live ordine).

### Campi nuovi su `InvoiceCreateSchema`

| Campo | Tipo | Obbligatorio | Default |
|-------|------|--------------|---------|
| `id_order` | int `> 0` | sì | — |
| `is_partial` | bool | no | `false` |
| `items` | `{ id_order_detail: int, quantity: number }[]` | se `is_partial === true` | omesso |
| `include_shipping` | bool | no | `true` se non parziale; `false` se parziale |

`quantity` può essere decimale (stesso vincolo qty NC). `id_order_detail` deve appartenere all’ordine.

Non accettare `order_line_items` (nome FE legacy). Canone = **`items`**, come NC.

### Regole

**A — Fattura sul residuo (default, `is_partial` omesso/false, `items` omesso)**

- Snapshot = tutte le righe fatturabili: `product_qty − qty già in resi − qty già in `fiscal_document_details` di fatture dell’ordine`.
- Non duplicare qty già fatturate.
- Resi esclusi (regola già documentata).
- Spedizione inclusa se `include_shipping` non è `false` **e** la spedizione non è già stata interamente attribuita a una fattura precedente.
- `is_partial: false` + `items: []` / `items: null` → trattare come omesso (residuo), non 422.

**B — Fattura parziale (`is_partial: true`)**

- `items` obbligatorio, `minItems: 1`. Assente / `[]` / `null` → **422** Pydantic (messaggio con `items` e `is_partial`, stesso stile NC).
- Snapshot = **solo** le coppie `id_order_detail` + `quantity`.
- Ogni `quantity` deve essere `> 0` e `≤ residuo` di quella riga. Superamento → **422** chiaro (riga, qty chiesta, residuo).
- `id_order_detail` sconosciuto / altro ordine → **422**.
- `include_shipping` default **false**. Se `true`, aggiungere riga spedizione snapshot (se costo ordine > 0 e non già interamente fatturata).
- Totali documento (`total_price_*`, `products_total_*`, `shipping_total_*`, `includes_shipping`) calcolati **solo** da questo snapshot.

**C — Riemissione (FE: `items` valorizzato, `is_partial` omesso/false)**

- Se `items` è presente e `is_partial` non è true: snapshot esplicito da `items` (qty live, resi già esclusi dal FE).
- Serve a re-emettere un documento sulle righe vive anche se esistono fatture precedenti. Non è un PATCH della fattura vecchia.
- Validare qty `> 0` e `id_order_detail` dell’ordine. Non applicare il tetto “residuo” (è riemissione).

**D — Extra**

- `extra=ignore` o schema chiuso: non rompere i client che mandano ancora `emitter_country_iso` / `invoice_flow` / CAP estero. Se si chiude lo schema, avvisare il FE.
- `is_electronic` resta sempre true lato server (come oggi). Il FE può continuare a mandarlo.

### GET dopo create

`GET /fiscal_documents/{id}` e `GET /orders/{id}/invoices` devono esporre `order_details` dello **snapshot fattura** (qty/prezzi fatturati), non le righe live dell’ordine. Altrimenti lista/dettaglio e il residuo FE (`aggregateInvoicedQuantitiesFromInvoices`) rifatturano o nascondono qty.

`includes_shipping` coerente con lo snapshot.

Bulk `POST .../invoices/bulk-create` resta **solo fatture piene sul residuo** (niente `items` per-ordine). Fuori scope.

---

## Errori

| Caso | HTTP |
|------|------|
| `is_partial: true` senza `items` / `items: []` | **422** |
| qty > residuo (parziale) | **422** |
| `id_order_detail` non dell’ordine | **422** |
| body `order_ids` / id non valido (invariato) | **422** / **404** |
| extra forbid se si decide di chiudere lo schema | **422** |

---

## Test BE attesi

1. POST `{ id_order }` su ordine 2 righe → 201, snapshot entrambe, totali = ordine (meno resi).
2. POST parziale 1 riga / qty &lt; residuo → 201, `order_details` solo quella qty, totali parziali, `includes_shipping=false` se non richiesto.
3. Stesso ordine, seconda POST `{ id_order }` (senza items) → 201 solo sul **residuo**, non rifattura la qty del punto 2.
4. POST `is_partial: true` senza `items` → **422**.
5. POST parziale qty &gt; residuo → **422**.
6. Riemissione: POST `items` = righe vive, senza `is_partial` → 201 anche se esiste già una fattura.

---

## Fuori scope

- Non introdurre PATCH-dopo-create per simulare la parziale.
- Non cambiare bulk-create, generate-xml, send-to-sdi.
- Non usare `order_line_items` come nome campo.

Handoff FE (repo Angular): payload già allineato a questo contratto in `buildCreateInvoiceRequest` (`items` + `is_partial`, niente PATCH).
