# Prompt FE — Allineamento Ricevuta API v3 (modelli + interpolazioni)

Incolla questo intero messaggio in chat sul **repo Angular del gestionale**.

---

## Contesto

Il backend **ECommerceManagerAPI** espone il contratto **Ricevuta v3** su:

- `GET /api/v1/ricevute/{id_ricevuta}` (dettaglio)
- `POST /api/v1/ricevute` / `PUT /api/v1/ricevute/{id}` (stesso shape del dettaglio)

Handoff BE aggiornato: `docs/FE_HANDOFF_RICEVUTE.md` (repo API).

**Obiettivo sessione:** allineare `ricevuta.model.ts`, componenti lista/dettaglio/stampa/export e **tutte le interpolazioni template** al contratto v3. Niente secondo fetch ordine per compile ricevuta.

---

## ⚠️ Breaking changes rispetto al codice FE attuale

### 1. Oggetto `order` rimosso

Non esiste più `detail.order`. I campi ordine sono in **root**.

| ❌ Vecchio (template / TS) | ✅ Nuovo v3 |
|---------------------------|-------------|
| `detail.order.id_order` | `detail.id_order` |
| `detail.order.reference` | `detail.order_reference` |
| `detail.order.is_payed` | `detail.is_payed` |
| `detail.order.payment_date` | `detail.data_incasso` |
| `detail.order.total_price_with_tax` | `detail.total_price_with_tax` |
| `detail.order.products_total_price_with_tax` | `detail.products_total_price_with_tax` |
| `detail.order.shipping_total_price_with_tax` | `detail.shipping_total_price_with_tax` |
| `detail.order.id_order_state` | `detail.id_order_state` |

### 2. Duplicazioni rimosse (2026-07-16)

| Dato | ❌ Non usare più | ✅ Fonte unica |
|------|-----------------|----------------|
| ID cliente | `detail.id_customer` (root) | `detail.customer?.id_customer` |
| Prezzo spedizione lordo | `detail.shipping?.price_tax_incl` | `detail.shipping_total_price_with_tax` |
| Prezzo spedizione netto | `detail.shipping?.price_tax_excl` | `detail.shipping_total_price_net` |
| Data pagamento / incasso | `detail.payment_date` | `detail.data_incasso` |

`shipping` = solo **contesto logistico** (corriere, aliquota, peso, messaggio).

### 3. Lista ≠ Dettaglio

`GET /api/v1/ricevute` (lista) **non** contiene: `payment`, `shipping`, `vies_status`, totali breakdown, `order_details`, indirizzi.

La pagina dettaglio **deve** chiamare `GET /api/v1/ricevute/{id}` — non riusare la riga lista.

### 4. Altri rename già noti

| ❌ Vecchio | ✅ Nuovo |
|-----------|---------|
| `detail.righe` | `detail.order_details` |
| `detail.pdf_hash` | rimosso |
| `order.is_modifiable` | `detail.is_modifiable` |

---

## TypeScript — `ricevuta.model.ts` (target)

Sostituire/aggiornare le interface. **Rimuovere** `RicevutaOrderSummary` e la proprietà `order` da `RicevutaDetail`.

```typescript
export type RicevutaStato = 'emessa' | 'annullata';

export interface RicevutaCustomerSummary {
  id_customer: number;
  firstname: string | null;
  lastname: string | null;
  email: string | null;
}

export interface RicevutaPayment {
  id_payment: number;
  name: string;
}

export interface RicevutaCarrierApi {
  id_carrier_api: number;
  name: string | null;
}

export interface RicevutaTax {
  id_tax: number;
  code: string | null;
  percentage: number | null;
  name: string | null;
}

/** Contesto logistico — NO prezzi (vedi shipping_total_price_* in root) */
export interface RicevutaShipping {
  id_shipping: number;
  carrier_api: RicevutaCarrierApi | null;
  tax: RicevutaTax | null;
  weight: number | null;
  shipping_message: string | null;
}

export interface RicevutaOrderDetail {
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

export interface RicevutaDetail {
  id_ricevuta: number;
  numero: number;
  anno: number;
  data_incasso: string;
  data_emissione: string;
  stato: RicevutaStato;
  pdf_path: string | null;
  pdf_generated_at: string | null;
  created_at: string;
  updated_at: string;
  annullata_at: string | null;
  annullata_da_user_id: number | null;
  is_modifiable: boolean;

  id_order: number;
  order_reference: string | null;
  id_order_state: number | null;
  total_weight: number | null;

  vies_status: 'eligible' | 'not_eligible' | null;
  is_payed: boolean;
  payment_due_date: string | null;
  payment: RicevutaPayment | null;
  shipping: RicevutaShipping | null;

  total_price_with_tax: number;
  total_price_net: number | null;
  products_total_price_with_tax: number | null;
  products_total_price_net: number | null;
  shipping_total_price_with_tax: number | null;
  shipping_total_price_net: number | null;
  total_discounts: number | null;

  customer: RicevutaCustomerSummary | null;
  address_delivery: RicevutaAddress | null;
  address_invoice: RicevutaAddress | null;
  order_details: RicevutaOrderDetail[];
}

export interface RicevutaListItem {
  id_ricevuta: number;
  numero: number;
  anno: number;
  id_order: number;
  data_incasso: string;
  data_emissione: string;
  stato: RicevutaStato;
  pdf_path: string | null;
  pdf_generated_at: string | null;
  customer: RicevutaCustomerSummary | null;
  order_reference: string | null;
  order_total_with_tax: number | null;
}
```

---

## Mapping UI — sezione per sezione

### Header documento

| UI | Interpolazione |
|----|----------------|
| Numero ricevuta | `{{ detail.numero }}/{{ detail.anno }}` |
| Data emissione | `detail.data_emissione` (ISO datetime) |
| Data incasso | `detail.data_incasso` |
| Stato | `detail.stato` |
| Modificabile | `detail.is_modifiable` (warning se false, non bloccare azioni) |

### Link ordine

| UI | Interpolazione |
|----|----------------|
| ID ordine (router) | `detail.id_order` |
| Riferimento ordine | `detail.order_reference ?? detail.id_order` |

### Cliente

| UI | Interpolazione |
|----|----------------|
| ID cliente | `detail.customer?.id_customer` |
| Nome | `detail.customer?.firstname` + `detail.customer?.lastname` |
| Email | `detail.customer?.email` |

### Indirizzi

Usare `detail.address_delivery` (consegna) e `detail.address_invoice` (fatturazione). Entrambi nullable.

| UI | Interpolazione |
|----|----------------|
| Ragione sociale | `address.company` |
| Indirizzo | `address.address1`, `address.address2` |
| Città / CAP | `address.city`, `address.postcode` |
| Paese | `address.country?.name` o `address.country?.iso_code` |
| P.IVA | `address.vat` |

### Pagamento

| UI | Interpolazione |
|----|----------------|
| Metodo | `detail.payment?.name` |
| Pagato | `detail.is_payed` |
| Data incasso | `detail.data_incasso` |
| Scadenza pagamento | `detail.payment_due_date` |
| VIES | `detail.vies_status` (`eligible` / `not_eligible` / null) |

### Spedizione (logistica)

| UI | Interpolazione |
|----|----------------|
| Corriere | `detail.shipping?.carrier_api?.name` |
| Peso ordine (totale kg) | `detail.total_weight` |
| Peso spedizione (record shipping) | `detail.shipping?.weight` |
| Aliquota spedizione | `detail.shipping?.tax?.percentage`, `detail.shipping?.tax?.name` |
| Messaggio | `detail.shipping?.shipping_message` |

### Totali (footer)

| UI | Interpolazione |
|----|----------------|
| Totale prodotti lordo | `detail.products_total_price_with_tax` |
| Totale prodotti netto | `detail.products_total_price_net` |
| Spedizione lordo | `detail.shipping_total_price_with_tax` |
| Spedizione netto | `detail.shipping_total_price_net` |
| Sconti | `detail.total_discounts` |
| **Totale documento lordo** | `detail.total_price_with_tax` |
| **Totale documento netto** | `detail.total_price_net` |

> **Attenzione doppio conteggio:** in `order_details[]` può esserci una riga `is_shipping: true` (Spedizione). I totali footer usano `shipping_total_price_*` e `total_price_*` — **non** sommare di nuovo la riga spedizione sui totali header.

### Righe tabella

```html
<tr *ngFor="let row of detail.order_details">
  <td>{{ row.product_reference }}</td>
  <td>{{ row.product_name }}</td>
  <td>{{ row.product_qty }}</td>
  <td>{{ row.unit_price_with_tax | currency }}</td>
  <td>{{ row.total_price_with_tax | currency }}</td>
</tr>
```

---

## Checklist refactor (grep nel repo FE)

Eseguire ricerca globale e correggere ogni occorrenza:

```text
.detail.order
detail?.order
RicevutaOrderSummary
\.order\.reference
\.order\.total_price
\.order\.id_order
detail\.id_customer          # root — usare customer.id_customer
shipping\.price_tax_incl
shipping\.price_tax_excl
shipping\?\.price_tax
righe
pdf_hash
```

Verificare file tipici:

- `src/app/core/models/ricevuta.model.ts`
- `src/app/core/services/ricevute.service.ts`
- `src/app/**/ricevut*.component.ts|html`
- pipe/formatters condivisi per stampa/export client-side (se presenti)

---

## Service — nessun cambio URL

```typescript
getRicevuta(id: number): Observable<RicevutaDetail> {
  return this.http.get<RicevutaDetail>(`${this.apiBase}/api/v1/ricevute/${id}`);
}
```

Dettaglio: sempre questa chiamata all'apertura pagina / modale / preview stampa.

---

## Verifica manuale (DevTools)

1. Apri dettaglio ricevuta → Network → `GET .../ricevute/{id}`
2. Response JSON deve avere:
   - ✅ `id_order`, `order_reference`, `payment`, `shipping`, `total_price_with_tax`
   - ✅ `customer.id_customer`
   - ✅ `shipping_total_price_with_tax`
   - ❌ **no** chiave `order`
   - ❌ **no** `id_customer` in root
   - ❌ **no** `price_tax_incl` / `price_tax_excl` dentro `shipping`

3. Template: nessun campo undefined dove prima leggeva da `order.*`

---

## Definition of done

- [ ] `ricevuta.model.ts` allineato v3 (no `order`, no `price_tax_*` in shipping)
- [ ] Dettaglio carica `getRicevuta(id)` — lista usata solo per tabella
- [ ] Tutte le interpolazioni aggiornate (header, cliente, pagamento, spedizione, totali, righe)
- [ ] Link ordine usa `detail.id_order`
- [ ] Export/stampa client-side (se esiste) legge da `RicevutaDetail` v3
- [ ] Grep repo: zero match su `.order.` nel modulo ricevute
- [ ] Test manuale su almeno 1 ricevuta reale con payment + shipping popolati

---

## Note business (non dimenticare)

- Se l'ordine cambia (es. reso con sostituzione): **DELETE ricevuta + POST nuova** (riemissione). Il documento non si aggiorna da solo.
- `is_modifiable === false` → ordine in Spedizione Confermata: mostrare warning, BE non blocca PUT/DELETE.
