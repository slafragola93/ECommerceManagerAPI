# Prompt FE — Pagamenti multipli per ordine (allineamento BE 2026-07-30)

Incolla questo intero messaggio in chat sul **repo Angular del gestionale**.

---

## Contesto

Il backend **ECommerceManagerAPI** supporta **più pagamenti/incassi** sullo stesso ordine (senza rate/scadenze).

Caso d’uso tipico:

1. Ordine già **Pagato**
2. Si aggiunge una riga prodotto → totale aumenta → BE imposta `is_payed = false`
3. L’operatore crea un **nuovo pagamento** per la differenza (`POST .../payments`)
4. Quando l’incasso è confermato, l’operatore marca di nuovo l’ordine come pagato (`PATCH .../payment?is_payed=true`)

**Obiettivo sessione:** aggiornare UI dettaglio ordine (sezione Pagamenti), modelli TypeScript e flussi dopo `add order_detail`, usando il contratto BE reale.

Doc BE: `README.mdc` sezione «Ultime modifiche (2026-07-30) — Pagamenti multipli».

---

## Distinzioni importanti (non confondere)

| Concetto | Endpoint / campi | Ruolo |
|----------|------------------|-------|
| Catalogo metodi | `GET /api/v1/payments` | Bonifico, Carta, … (`id_payment`, `name`) |
| Metodo principale ordine (legacy) | `order.payment` / `id_payment` | Un solo metodo “default” (checkout / FatturaPA) |
| Flag pagato ordine (legacy) | `order.is_payed`, `payment_date`, `payment_due_date` | Stato globale ordine |
| **Lista incassi** | `/api/v1/orders/{id}/payments` | **Nuovo:** N pagamenti con importo |

Naming BE: ordine usa `is_payed`; singola riga pagamento usa `is_paid`. Non unificare i nomi lato API; in FE si possono mappare a `isOrderPaid` / `isPaymentPaid`.

**Non sono rate:** nessun `due_date` per riga, nessun TP03 FatturaPA. Ogni riga è un incasso standalone con `amount`.

---

## Contratto TypeScript

```ts
interface OrderPaymentMethodEmbed {
  id_payment: number;
  name: string;
}

interface OrderPayment {
  id_order_payment: number;
  id_order: number;
  id_payment: number;
  amount: number;
  is_paid: boolean;
  payment_date: string | null; // YYYY-MM-DD
  note: string | null;
  date_add: string | null;     // datetime ISO
  payment: OrderPaymentMethodEmbed | null;
}

interface OrderPaymentSummary {
  total_scheduled: number; // somma di tutti gli amount
  total_paid: number;      // somma amount dove is_paid=true
  remaining_amount: number; // order.total_price_with_tax - total_paid
}

interface OrderPaymentsListResponse {
  order_payments: OrderPayment[];
  payment_summary: OrderPaymentSummary;
  total: number;
}

interface OrderPaymentCreate {
  id_payment: number;       // > 0, da catalogo /init o /payments
  amount: number;           // > 0
  is_paid?: boolean;        // default false
  payment_date?: string | null; // YYYY-MM-DD; se is_paid=true e omessa → oggi (BE)
  note?: string | null;     // max 200
}

interface OrderPaymentUpdate {
  id_payment?: number;
  amount?: number;
  note?: string | null;
}

interface OrderPaymentPaidStatus {
  is_paid: boolean;
  payment_date?: string | null; // YYYY-MM-DD
}
```

Nel **dettaglio ordine** (`GET /api/v1/orders/{id}` con `show_details`):

```ts
// campi aggiuntivi sulla response ordine
order_payments?: OrderPayment[];
payment_summary?: OrderPaymentSummary;
// legacy invariati:
is_payed: boolean;
payment?: { id_payment: number; name: string } | null;
payment_date?: string | null;
payment_due_date?: string | null;
```

In **lista ordini** `order_payments` / `payment_summary` **non** sono garantiti: usare dettaglio o `GET .../payments`.

---

## Endpoint

Base: `/api/v1/orders/{order_id}/payments`  
Permessi: `orders:read` (GET), `orders:update` (POST/PUT/PATCH/DELETE).

| Metodo | Path | Body | Risposta |
|--------|------|------|----------|
| GET | `/api/v1/orders/{order_id}/payments` | — | `OrderPaymentsListResponse` |
| POST | `/api/v1/orders/{order_id}/payments` | `OrderPaymentCreate` | `OrderPayment` (201) |
| PUT | `/api/v1/orders/{order_id}/payments/{id_order_payment}` | `OrderPaymentUpdate` | `OrderPayment` |
| PATCH | `/api/v1/orders/{order_id}/payments/{id_order_payment}` | `OrderPaymentPaidStatus` | `OrderPayment` |
| DELETE | `/api/v1/orders/{order_id}/payments/{id_order_payment}` | — | `{ message, id_order_payment, order_id }` |

### Legacy (resta)

| Metodo | Path | Uso |
|--------|------|-----|
| PATCH | `/api/v1/orders/{order_id}/payment?is_payed=true\|false` | Marca ordine pagato/non pagato |
| PATCH | `/api/v1/orders/{order_id}/payment?payment_due_date=YYYY-MM-DD` | Scadenza unica ordine |

Almeno uno tra `is_payed` e `payment_due_date` obbligatorio.

---

## Esempi payload

### POST — nuovo pagamento dopo aggiunta prodotto

```http
POST /api/v1/orders/123/payments
Content-Type: application/json
```

```json
{
  "id_payment": 3,
  "amount": 49.90,
  "is_paid": false,
  "note": "Pagamento nuovo articolo"
}
```

### PATCH — segna riga incassata

```http
PATCH /api/v1/orders/123/payments/45
Content-Type: application/json
```

```json
{
  "is_paid": true
}
```

### PATCH — conferma ordine pagato (legacy)

```http
PATCH /api/v1/orders/123/payment?is_payed=true
```

---

## Regole BE che il FE deve rispettare

1. **Creazione pagamenti = manuale.** Dopo `POST /orders/{id}/order_detail` il BE **non** crea automaticamente un `order_payment`. Il FE deve proporre/creare il pagamento (es. importo = `payment_summary.remaining_amount` o delta calcolato).
2. **`is_payed` auto → `false`** quando:
   - si aggiunge/modifica una riga e il **totale ordine aumenta**;
   - si crea un pagamento con `is_paid: false`;
   - si segna una riga `is_paid: false` (o copertura insufficiente con `order_payments` presenti).
3. **`is_payed` non diventa mai `true` da solo.** Solo `PATCH .../payment?is_payed=true`.
4. **Somma rate/importi non è vincolo rigido:** si può creare un pagamento anche se `amount` ≠ `remaining_amount`. Usare `payment_summary` solo come guida UI.
5. **Nessun link a `id_order_detail`:** il pagamento non è collegato alla riga prodotto.
6. Catalogo metodi: riusare init/`GET /payments` per la select `id_payment`.

---

## Flusso UI consigliato

```text
[Dettaglio ordine — sezione Pagamenti]

1. Badge stato: order.is_payed ? "Pagato" : "Non pagato"
2. Tabella order_payments:
   - metodo (payment.name)
   - importo
   - is_paid (toggle → PATCH .../payments/{id})
   - payment_date / note
   - azioni: modifica (PUT), elimina (DELETE)
3. Summary:
   - Programmato: payment_summary.total_scheduled
   - Incassato: payment_summary.total_paid
   - Residuo: payment_summary.remaining_amount
4. CTA "Aggiungi pagamento" → dialog POST
   - default amount = max(remaining_amount, 0) se > 0
   - default is_paid = false
5. Dopo add order_detail:
   - se is_payed passa a false → toast / highlight "Ordine non più completamente pagato"
   - aprire o suggerire "Aggiungi pagamento" con delta
6. Quando residuo ≈ 0 e tutte le righe is_paid:
   - CTA "Segna ordine come pagato" → PATCH .../payment?is_payed=true
```

---

## Checklist implementazione FE

- [ ] Modelli/interfacce `OrderPayment`, `OrderPaymentSummary`, create/update/paid
- [ ] Service HTTP nested sotto `orders/{id}/payments`
- [ ] Sezione UI dettaglio ordine: lista + summary + CRUD
- [ ] Dopo `addOrderDetail` / update riga: rileggere ordine e reagire a `is_payed === false`
- [ ] Non auto-settare `is_payed=true` lato FE senza conferma operatore (o chiamata PATCH legacy)
- [ ] Distinguere catalogo `/payments` da lista `/orders/{id}/payments`
- [ ] Lista ordini: continuare a usare `is_payed` (flag); dettaglio per i multi-pagamenti
- [ ] i18n etichette IT (Pagamenti, Incassato, Residuo, Aggiungi pagamento, …)

---

## Fuori scope (non implementare in FE su questo BE)

- Rate con date scadenza per riga
- Collegamento pagamento ↔ `order_detail`
- Auto `is_payed=true` quando somma incassi ≥ totale
- Multi-blocco FatturaPA da `order_payments`
- Sync PrestaShop dei pagamenti multipli

---

## Smoke test FE

1. Ordine pagato con totale 100 → aggiungi articolo 50 → verifica badge **Non pagato** e totale 150.
2. `POST .../payments` amount 50, `is_paid: false` → riga in tabella, `remaining_amount` coerente.
3. `PATCH .../payments/{id}` `{ "is_paid": true }` → riga incassata, summary aggiornato.
4. `PATCH .../payment?is_payed=true` → ordine di nuovo **Pagato**.
5. Delete/edit pagamento → summary e UI coerenti dopo refresh.
