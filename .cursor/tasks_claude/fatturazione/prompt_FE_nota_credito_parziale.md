# Prompt FE — Documenti fiscali unificati (fattura + nota di credito)

Copia tutto il contenuto **sotto la riga `---`** e incollalo in una nuova chat Cursor sul **repository del gestionale Angular**.

Handoff BE (repo **ECommerceManagerAPI**):

- Contratto unico: **`InvoiceDetail` v3** per fatture **e** note di credito (`document_type` discrimina)
- Modale NC parziale: `GET .../details-with-products`
- Export bulk: stesso endpoint fatture con `document_type=credit_note`
- Doc: [`docs/FATTURAPA.md`](../../../docs/FATTURAPA.md)

**Obiettivo sessione:** allineare modelli, service e UI note di credito al **medesimo payload delle fatture**, più campi NC-specifici.

---

## Principio architetturale BE (2026-07-22)

| Prima | Ora |
|-------|-----|
| NC con `CreditNoteResponseSchema` minimale (`details[]` flat) | NC con **`InvoiceResponseSchema` v3** (alias `CreditNoteResponseSchema`) |
| `GET /{id}` NC → payload generico ORM | `GET /{id}` NC → stesso shape di fattura + campi NC |
| Export solo `document_type=invoice` | Export con query **`document_type=invoice\|credit_note`** |

**Regola FE:** un solo modello TypeScript `FiscalDocumentDetail` (o `InvoiceDetail`) per fattura e NC. Branch UI su `document_type`.

---

## Modello TypeScript unificato

```typescript
export type FiscalDocumentType = 'invoice' | 'credit_note';

/** Stesso contratto per GET/POST fattura e GET/POST nota di credito */
export interface FiscalDocumentDetail {
  id_fiscal_document: number;
  document_type: FiscalDocumentType;
  tipo_documento_fe?: string | null; // TD01 | TD04
  id_order: number;

  // Solo credit_note (null/undefined su invoice)
  id_fiscal_document_ref?: number | null;
  credit_note_reason?: string | null;
  is_partial?: boolean | null;

  document_number?: string | null;
  internal_number?: string | null;
  filename?: string | null;
  xml_content?: string | null;
  status: string;
  is_electronic: boolean;
  upload_result?: string | null;
  includes_shipping: boolean;

  total_price_with_tax?: number | null;
  total_price_net?: number | null;
  products_total_price_net?: number | null;
  products_total_price_with_tax?: number | null;
  date_add?: string | null;
  date_upd?: string | null;

  order_reference?: string | null;
  id_order_state?: number | null;
  total_weight?: number | null;
  vies_status?: string | null;
  is_payed: boolean;
  payment_due_date?: string | null;

  payment?: PaymentEmbed | null;
  shipping?: ShippingEmbed | null;
  shipping_total_price_with_tax?: number | null;
  shipping_total_price_net?: number | null;
  total_discounts?: number | null;

  customer?: CustomerEmbed | null;
  address_delivery?: AddressEmbed | null;
  address_invoice?: AddressEmbed | null;

  /** Righe snapshot documento (prodotti + eventuale riga Spedizione is_shipping=true) */
  order_details: OrderDetailEmbed[];
}

/** Alias retrocompatibile */
export type InvoiceDetail = FiscalDocumentDetail;
export type CreditNoteDetail = FiscalDocumentDetail;
```

**Rimuovere** modelli separati con solo `details[]` flat se ancora presenti.

---

## API — dettaglio documento

```http
GET /api/v1/fiscal_documents/{id}
```

- `document_type=invoice` → payload v3 (già noto)
- `document_type=credit_note` → **stesso payload** + `id_fiscal_document_ref`, `credit_note_reason`, `is_partial`

```http
POST /api/v1/fiscal_documents/credit-notes
```

Response **201**: `FiscalDocumentDetail` (non più schema minimale).

```http
GET /api/v1/fiscal_documents/credit-notes/invoice/{id_invoice}
```

Response: `FiscalDocumentDetail[]` arricchite (stesso shape del GET singolo).

---

## API — modale NC parziale (pre-submit)

```http
GET /api/v1/fiscal_documents/{id_invoice}/details-with-products
```

Payload **leggero** solo per modale (qty residue). Dopo submit usare `GET /{id}` per dettaglio completo.

Vedi sezione modale nel prompt precedente (`CreditNoteEligibleLinesResponse`).

---

## API — export bulk (fatture **e** note di credito)

```http
GET /api/v1/fiscal_documents/invoices/export?fmt=xlsx|xml&document_type=invoice|credit_note
```

| Param | Note |
|-------|------|
| `document_type` | Default `invoice`. Usare `credit_note` per export NC |
| `fmt=xlsx` | Foglio «Note di credito» se `document_type=credit_note` |
| `fmt=xml` | ZIP XML FatturaPA TD04 |
| PDF bulk | ❌ non disponibile — solo `GET /{id}/pdf` singolo |

**Filename BE:**

- Fatture: `fatture-export*.xlsx`, `fatture-xml-export*.zip`
- NC: `note-credito-export*.xlsx`, `note-credito-xml-export*.zip`

**Service Angular:**

```typescript
exportInvoicesBulk(options: {
  fmt: 'xlsx' | 'xml';
  document_type?: 'invoice' | 'credit_note';
  delivery_country_iso?: string;
  date_add_from?: string;
  date_add_to?: string;
  // filtri Excel aggiuntivi: status, is_electronic, id_order, id_customer
}) { ... }
```

Menu export lista NC: stessa UI export fatture, param `document_type=credit_note`.

---

## UI — checklist

### Dettaglio / lista NC

- [ ] Tipizzare dettaglio NC con `FiscalDocumentDetail` (non schema legacy)
- [ ] Riutilizzare componenti dettaglio fattura (cliente, indirizzi, `order_details`, totali)
- [ ] Mostrare badge NC: `credit_note_reason`, link fattura ref (`id_fiscal_document_ref`)
- [ ] PDF / generate-xml / send-to-sdi: stessi bottoni fattura su `id_fiscal_document` NC

### Modale creazione NC parziale

- [ ] `GET .../details-with-products` all'apertura
- [ ] `POST .../credit-notes` → navigare a dettaglio con response v3
- [ ] Validazione qty vs `remaining_qty`

### Export

- [ ] Aggiungere export NC in lista (o filtro tipo documento) con `document_type=credit_note`
- [ ] Non duplicare logica download: riusare helper export fatture

---

## POST creazione NC — payload invariato

```json
{
  "id_invoice": 62,
  "reason": "Reso parziale",
  "is_partial": true,
  "include_shipping": false,
  "items": [{ "id_order_detail": 456, "quantity": 2 }]
}
```

Response ora include `order_details[]`, `customer`, `address_invoice`, ecc.

---

## Test manuali FE

1. Dettaglio NC → stessi blocchi UI della fattura + motivo + ref fattura
2. POST NC parziale → response con `order_details` popolato
3. Lista NC per fattura → array v3 arricchito
4. Export Excel NC → file `note-credito-export*.xlsx`
5. Export XML NC → ZIP con TD04
6. PDF singola NC → `GET /{id_nc}/pdf`
