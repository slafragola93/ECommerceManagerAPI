# Prompt FE — Allineamento Fattura GET v3 (modelli + interpolazioni)

Incolla questo intero messaggio in chat sul **repo Angular del gestionale**.

---

## Contesto

Il backend **ECommerceManagerAPI** espone il contratto **Fattura v3** (allineato a Ricevuta v3 per il contesto ordine) su:

| Metodo | Path | Note |
|--------|------|------|
| GET | `/api/v1/fiscal_documents/invoices/order/{id_order}` | Tutte le fatture dell'ordine — **response arricchita** |
| GET | `/api/v1/fiscal_documents/{id_fiscal_document}` | Se `document_type === 'invoice'` → stesso shape arricchito |
| POST | `/api/v1/fiscal_documents/invoices` | Dopo creazione → stesso shape del GET dettaglio |

Handoff BE: sezione *Fattura GET allineata a ricevuta v3* in `README.md` (repo API).

**Obiettivo sessione:** allineare `invoice.model.ts` (o equivalente), componenti dettaglio/preview/stampa fattura e **tutte le interpolazioni template** al contratto v3. **Eliminare il secondo fetch ordine** usato solo per compilare cliente/indirizzi/pagamento/spedizione/righe.

---

## ⚠️ Breaking changes rispetto al codice FE attuale

### 1. Response prima era “solo documento”

Prima `GET .../invoices/order/{id}` e `POST .../invoices` restituivano solo campi fiscali (`id_fiscal_document`, numeri, status, totali documento). Il FE probabilmente faceva anche `GET /api/v1/orders/{id}` per cliente, indirizzi, righe, pagamento.

**Ora** tutto è in un’unica response `InvoiceDetail` — **non** refetchare l’ordine per la UI fattura (salvo navigazione esplicita “Vai all’ordine”).

### 2. Totali = snapshot documento (≠ ordine live)

| Campo | Fonte |
|-------|--------|
| `total_price_*`, `products_total_*` | **Documento fiscale** al momento emissione |
| `shipping_total_price_*` | Derivati dal documento (`totale − prodotti`) o fallback ordine |
| `total_discounts` | Contesto ordine (informativo) |

**Non** sostituire con `order.total_price_*` dopo il load fattura.

### 3. Righe = snapshot fiscale (≠ ricevuta live)

| Documento | `order_details[]` |
|-----------|-------------------|
| **Ricevuta** | Righe **live** da ordine |
| **Fattura** | Snapshot `fiscal_document_details` + riga spedizione sintetica |

Prezzi riga = quelli **fatturati** (con sconti già applicati nel totale riga). Nome/reference prodotto arricchiti dal collegamento `id_order_detail`.

### 4. Embed condivisi con Ricevuta v3

Stessa semantica di `RicevutaDetail` per:

- `customer`, `address_delivery`, `address_invoice`
- `payment` → solo `{ id_payment, name }`
- `shipping` → **solo logistico** (corriere, tax, peso, messaggio) — **NO** `price_tax_incl` / `price_tax_excl`
- Importi spedizione → `shipping_total_price_with_tax` / `shipping_total_price_net` in **root**

### 5. Lista generica ≠ Dettaglio fattura

`GET /api/v1/fiscal_documents/` (lista paginata) resta **minimal** (`FiscalDocumentResponseSchema` senza embed).

Per dettaglio UI fattura usare **sempre** uno degli endpoint arricchiti sopra — non la riga lista.

### 6. Campi solo fattura (non confondere con ricevuta)

| Fattura | Ricevuta (non usare su fattura) |
|---------|----------------------------------|
| `id_fiscal_document` | `id_ricevuta` |
| `document_number`, `internal_number` | `numero`, `anno` |
| `tipo_documento_fe` (TD01, …) | — |
| `status` (pending, issued, sent, …) | `stato` (emessa/annullata) |
| `is_electronic`, `xml_content`, `upload_result` | — |
| `includes_shipping` | — |
| `date_add`, `date_upd` | `data_emissione`, `data_incasso`, … |
| — | `is_modifiable`, PDF ricevuta |

---

## TypeScript — tipi condivisi + `invoice.model.ts`

**Consiglio:** estrarre embed riusabili (già usati da ricevuta v3) in `fiscal-embed.model.ts`:

```typescript
// fiscal-embed.model.ts — identici a Ricevuta v3
export interface FiscalCustomerSummary {
  id_customer: number;
  firstname: string | null;
  lastname: string | null;
  email: string | null;
}

export interface FiscalCountry {
  iso_code: string | null;
  name: string | null;
}

export interface FiscalAddress {
  id_address: number;
  company: string | null;
  firstname: string | null;
  lastname: string | null;
  address1: string | null;
  address2: string | null;
  city: string | null;
  postcode: string | null;
  state: string | null;
  phone: string | null;
  vat: string | null;
  country: FiscalCountry | null;
}

export interface FiscalPayment {
  id_payment: number;
  name: string;
}

export interface FiscalCarrierApi {
  id_carrier_api: number;
  name: string | null;
}

export interface FiscalTax {
  id_tax: number;
  code: string | null;
  percentage: number | null;
  name: string | null;
}

/** Contesto logistico — NO prezzi (vedi shipping_total_price_* in root) */
export interface FiscalShipping {
  id_shipping: number;
  carrier_api: FiscalCarrierApi | null;
  tax: FiscalTax | null;
  weight: number | null;
  shipping_message: string | null;
}

export interface FiscalOrderDetailLine {
  id_order_detail: number;
  id_product: number | null;
  product_name: string | null;
  product_reference: string | null;
  product_qty: number;
  product_weight: number | null;
  id_tax: number | null;
  unit_price_net: number | null;
  unit_price_with_tax: number | null;
  total_price_net: number | null;
  total_price_with_tax: number | null;
  reduction_percent: number | null;
  reduction_amount: number | null;
  is_shipping: boolean;
}
```

**Target `InvoiceDetail`:**

```typescript
export type FiscalDocumentStatus =
  | 'pending'
  | 'issued'
  | 'generated'
  | 'uploaded'
  | 'sent'
  | 'processed'
  | 'cancelled'
  | 'error';

export interface InvoiceDetail {
  // --- Documento fiscale ---
  id_fiscal_document: number;
  document_type: 'invoice';
  tipo_documento_fe: string | null; // es. TD01
  id_order: number;
  document_number: string | null;
  internal_number: string | null;
  filename: string | null;
  xml_content: string | null;
  status: FiscalDocumentStatus;
  is_electronic: boolean;
  upload_result: string | null;
  includes_shipping: boolean;
  total_price_with_tax: number | null;
  total_price_net: number | null;
  products_total_price_net: number | null;
  products_total_price_with_tax: number | null;
  date_add: string;
  date_upd: string;

  // --- Contesto ordine (come ricevuta v3) ---
  order_reference: string | null;
  id_order_state: number | null;
  total_weight: number | null;
  vies_status: 'eligible' | 'not_eligible' | null;
  is_payed: boolean;
  payment_due_date: string | null;
  payment: FiscalPayment | null;
  shipping: FiscalShipping | null;
  shipping_total_price_with_tax: number | null;
  shipping_total_price_net: number | null;
  total_discounts: number | null;

  customer: FiscalCustomerSummary | null;
  address_delivery: FiscalAddress | null;
  address_invoice: FiscalAddress | null;
  order_details: FiscalOrderDetailLine[];
}
```

Se `RicevutaDetail` v3 è già allineato, **riusa** le interface embed (alias o import condiviso) — evita duplicazione.

---

## Mapping UI — sezione per sezione

### Header documento fiscale

| UI | Interpolazione |
|----|----------------|
| ID documento | `detail.id_fiscal_document` |
| Numero elettronico | `detail.document_number` |
| Numero interno | `detail.internal_number` |
| Tipo FE | `detail.tipo_documento_fe` (es. TD01) |
| Data emissione | `detail.date_add` (ISO datetime) |
| Ultimo aggiornamento | `detail.date_upd` |
| Stato workflow | `detail.status` |
| Elettronica | `detail.is_electronic` |
| Include spedizione | `detail.includes_shipping` |
| File XML | `detail.filename`, `detail.xml_content` (solo se serve preview/download) |
| Esito upload SDI | `detail.upload_result` (JSON string — parse se badge/alert) |

### Link ordine

| UI | Interpolazione |
|----|----------------|
| ID ordine (router) | `detail.id_order` |
| Riferimento | `detail.order_reference ?? detail.id_order` |
| Stato ordine | `detail.id_order_state` (label da lookup locale) |

### Cliente

| UI | Interpolazione |
|----|----------------|
| ID cliente | `detail.customer?.id_customer` |
| Nome | `detail.customer?.firstname` + `detail.customer?.lastname` |
| Email | `detail.customer?.email` |

### Indirizzi

Usare **`detail.address_invoice`** per intestazione fattura / FatturaPA; **`detail.address_delivery`** per consegna se mostrata. Entrambi nullable.

| UI | Interpolazione |
|----|----------------|
| Ragione sociale | `address.company` |
| Nome | `address.firstname`, `address.lastname` |
| Indirizzo | `address.address1`, `address.address2` |
| Città / CAP | `address.city`, `address.postcode` |
| Paese | `address.country?.name` o `address.country?.iso_code` |
| P.IVA | `address.vat` |

### Pagamento

| UI | Interpolazione |
|----|----------------|
| Metodo | `detail.payment?.name` |
| Pagato | `detail.is_payed` |
| Scadenza | `detail.payment_due_date` |
| VIES | `detail.vies_status` |

> **Nota:** la fattura non ha `data_incasso` — per date pagamento usare `payment_due_date` o navigazione ordine.

### Spedizione (logistica)

| UI | Interpolazione |
|----|----------------|
| Corriere | `detail.shipping?.carrier_api?.name` |
| Peso ordine totale | `detail.total_weight` |
| Peso record shipping | `detail.shipping?.weight` |
| Aliquota spedizione | `detail.shipping?.tax?.percentage` |
| Messaggio | `detail.shipping?.shipping_message` |

### Totali (footer) — **documento**

| UI | Interpolazione |
|----|----------------|
| Totale prodotti lordo | `detail.products_total_price_with_tax` |
| Totale prodotti netto | `detail.products_total_price_net` |
| Spedizione lordo | `detail.shipping_total_price_with_tax` (null se `includes_shipping === false`) |
| Spedizione netto | `detail.shipping_total_price_net` |
| Sconti (info ordine) | `detail.total_discounts` |
| **Totale fattura lordo** | `detail.total_price_with_tax` |
| **Totale fattura netto** | `detail.total_price_net` |

> **Doppio conteggio:** in `order_details[]` può esserci riga `is_shipping: true`. Footer = campi root — **non** sommare di nuovo la riga spedizione sui totali header.

### Righe tabella (snapshot)

```html
<tr *ngFor="let row of detail.order_details">
  <td>{{ row.product_reference }}</td>
  <td>{{ row.product_name }}</td>
  <td>{{ row.product_qty }}</td>
  <td>{{ row.unit_price_with_tax | currency }}</td>
  <td>{{ row.total_price_with_tax | currency }}</td>
  <td *ngIf="row.is_shipping">Spedizione</td>
</tr>
```

Riga con `id_order_detail === 0` e `is_shipping === true` = spedizione sintetica.

---

## Refactor consigliato — rimuovere doppio fetch

### ❌ Pattern vecchio (eliminare)

```typescript
forkJoin({
  invoice: this.http.get<InvoiceMinimal>(`.../invoices/order/${idOrder}`),
  order: this.http.get<OrderDetail>(`/api/v1/orders/${idOrder}`),
}).subscribe(({ invoice, order }) => {
  this.view = mergeInvoiceAndOrder(invoice, order);
});
```

### ✅ Pattern v3

```typescript
getInvoicesByOrder(idOrder: number): Observable<InvoiceDetail[]> {
  return this.http.get<InvoiceDetail[]>(
    `${this.apiBase}/api/v1/fiscal_documents/invoices/order/${idOrder}`
  );
}

getInvoice(idFiscalDocument: number): Observable<InvoiceDetail> {
  return this.http.get<InvoiceDetail>(
    `${this.apiBase}/api/v1/fiscal_documents/${idFiscalDocument}`
  );
}

createInvoice(body: { id_order: number; is_electronic: boolean }): Observable<InvoiceDetail> {
  return this.http.post<InvoiceDetail>(
    `${this.apiBase}/api/v1/fiscal_documents/invoices`,
    body
  );
}
```

Componente dettaglio: **una sola** chiamata → bind diretto su `InvoiceDetail`.

---

## Checklist refactor (grep nel repo FE)

```text
invoices/order
fiscal_documents/invoices
mergeInvoiceAndOrder
getOrder.*invoice
invoice.*getOrder
\.order\.reference          # nel modulo fatture — usare detail.order_reference
shipping\.price_tax_incl
shipping\.price_tax_excl
details\[                   # se mappato da FiscalDocumentDetailResponse — ora order_details
FiscalDocumentDetail
InvoiceMinimal
```

File tipici:

- `src/app/core/models/invoice.model.ts` / `fiscal-document.model.ts`
- `src/app/core/models/ricevuta.model.ts` (estrarre embed condivisi)
- `src/app/**/fattur*.component.ts|html`
- `src/app/**/invoice*.component.ts|html`
- service NgRx effects `fiscal_documents` / `invoices`

---

## Verifica manuale (DevTools)

1. Apri dettaglio fattura → Network → `GET .../fiscal_documents/{id}` o `.../invoices/order/{id_order}`
2. Response JSON deve avere:
   - ✅ `id_fiscal_document`, `document_number`, `status`, `tipo_documento_fe`
   - ✅ `order_reference`, `payment`, `shipping`, `customer`
   - ✅ `shipping_total_price_with_tax`
   - ✅ `order_details[]` con almeno una riga prodotto
   - ✅ `address_invoice` (per fattura IT)
   - ❌ **no** oggetto `order` annidato
   - ❌ **no** `price_tax_incl` / `price_tax_excl` dentro `shipping`
3. Confronto: totali response fattura **≠** totali ordine live se ordine modificato dopo emissione (comportamento atteso).

---

## Parità con Ricevuta v3 — tabella rapida

| Campo embed | Ricevuta | Fattura |
|-------------|----------|---------|
| `customer` | ✅ | ✅ |
| `address_delivery` / `address_invoice` | ✅ | ✅ |
| `payment` slim | ✅ | ✅ |
| `shipping` slim | ✅ | ✅ |
| `shipping_total_price_*` root | ✅ | ✅ |
| `order_details[]` | live ordine | **snapshot documento** |
| Totali root | ordine live | **documento fiscale** |
| Header doc | numero/anno ricevuta | numeri/status FE |

---

## Definition of done

- [ ] `InvoiceDetail` / modelli allineati v3 (embed condivisi con ricevuta dove possibile)
- [ ] Dettaglio fattura: **un solo GET** arricchito — niente merge con ordine
- [ ] Template aggiornati: header fiscale, cliente, indirizzo fatturazione, pagamento, spedizione, totali, righe
- [ ] Footer totali legge campi **documento**, non ordine
- [ ] Tabella righe usa `order_details` (non `details` legacy né righe ordine)
- [ ] POST creazione fattura: response tipizzata `InvoiceDetail` (no refetch)
- [ ] Grep: zero `shipping.price_tax_*` nel modulo fatture
- [ ] Test manuale: fattura con spedizione (`includes_shipping=true`) → 2 righe in tabella + totali coerenti

---

## Note business

- La fattura è **snapshot**: modifiche ordine post-emissione **non** aggiornano il documento — servono nota di credito / nuova fattura secondo regole BE.
- Ordine fatturato esce dai corrispettivi vendite; il FE non deve ricalcolare corrispettivi dalla fattura.
- Note di credito e resi: **non** coperti da questo prompt — contratto invariato (resi) o da allineare in sessione separata (NC).
- Permessi RBAC: `fiscal_documents:read` / `:create` come già in uso.

---

## Riferimenti BE (repo API)

- **Guida operativa:** [`docs/FATTURAPA.md`](../../docs/FATTURAPA.md) — workflow, POST body, VIES, troubleshooting
- Schema: `src/schemas/fiscal_document_schema.py` → `InvoiceResponseSchema`
- Mapper: `src/services/routers/fiscal_document_service.py`
- Prompt ricevuta analogo: `.cursor/tasks_claude/fatturazione/prompt_FE_ricevute_V3_ALIGN.md`
