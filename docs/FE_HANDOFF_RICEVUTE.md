3# FE — Ricevute estero (handoff BE)

Guida per il gestionale Angular (repo FE separato).  
**Prompt implementazione FE:** [.cursor/tasks_claude/fatturazione/prompt_FE_ricevute.md](../.cursor/tasks_claude/fatturazione/prompt_FE_ricevute.md)  
**Prompt test integrazione (incolla in chat FE):** [.cursor/tasks_claude/fatturazione/prompt_FE_ricevute_TEST.md](../.cursor/tasks_claude/fatturazione/prompt_FE_ricevute_TEST.md)

Riferimento BE task list: [.cursor/tasks_claude/fatturazione/TASKS_BE_ricevute.md](../.cursor/tasks_claude/fatturazione/TASKS_BE_ricevute.md)

---

## Stato implementazione BE

| Step | Stato | Note |
|------|-------|------|
| **BE-1** Schema DB `ricevute` | ✅ | migration: `python scripts/migrations/create_ricevute_table.py` |
| **BE-2.2** GET lista + dettaglio | ✅ | join live ordine/cliente/righe |
| **BE-2.1** POST creazione | ✅ | da modale ordine (`id_order`, `data_emissione` opz.) |
| **BE-2.3** PDF | ✅ | auto in POST; `GET/POST .../pdf` |
| **BE-2.4** PUT / DELETE | ✅ | DELETE = cancellazione definitiva; `is_modifiable` solo warning FE |
| BE-3 Corrispettivi | ✅ BE-3.1–3.3 | breakdown audit + compatibilità resi |
| BE-2.5 Export CSV/Excel | ✅ | singola + massiva |
| BE-2.6 Email | ⏳ | invio PDF |

Il FE può integrare **lista, dettaglio, creazione, PDF, eliminazione**.

---

## Contesto funzionale

Le **ricevute** sono documenti fiscali **interni** (no SDI) per clienti esteri privati senza P.IVA.

- Nessuna tabella righe persistita → prodotti/prezzi sempre **live** da `orders` / `order_details`
- Nessuno snapshot cliente → anagrafica live da `customers`
- Numerazione `{numero}/{anno}` (progressiva annuale)
- Modificabilità: derivata dallo **stato ordine**, non da un flag sulla ricevuta

---

## Autenticazione e permessi

| Aspetto | Valore |
|---------|--------|
| Base URL | `/api/v1/ricevute` |
| Header | `Authorization: Bearer <JWT>` |
| Permesso RBAC read | `fiscal_documents:read` |
| Permesso create | `fiscal_documents:create` |
| Permesso update | `fiscal_documents:update` |
| Permesso delete | `fiscal_documents:delete` |
| Swagger BE | tag **Ricevute** su `/docs` |

Stesso permesso dei **Corrispettivi** — se l’utente vede i corrispettivi, può leggere le ricevute.

---

## API disponibili

### GET lista

```http
GET /api/v1/ricevute?id_order=&id_customer=&stato=&data_emissione_from=&data_emissione_to=&page=1&limit=10
Authorization: Bearer <JWT>
```

| Query param | Tipo | Descrizione |
|-------------|------|-------------|
| `id_order` | int | Filtra per ordine collegato |
| `id_customer` | int | Filtra per cliente |
| `stato` | `"emessa"` \| `"annullata"` | Filtra per stato |
| `data_emissione_from` | `YYYY-MM-DD` | Range emissione (incluso) |
| `data_emissione_to` | `YYYY-MM-DD` | Range emissione (incluso) |
| `page` | int | Default `1` |
| `limit` | int | Default `10`, max `500` |

**Response 200:** `RicevutaListResponse`

Ordinamento BE: `data_emissione` DESC (data + ora), poi `numero` DESC.

---

### GET dettaglio

```http
GET /api/v1/ricevute/{id_ricevuta}
Authorization: Bearer <JWT>
```

**Response 200:** `RicevutaDetail` (header + `customer` + `order` + indirizzo/i + `order_details[]` live)

**Contratto v2 (snellito):** niente `id_order`/`id_customer`/`pdf_hash` in root; `is_modifiable` solo su root; indirizzi sempre in `address_delivery` e `address_invoice` (nullable, anche se coincidono).

**404:** ricevuta non trovata (standard FastAPI `{ "detail": "..." }`).

---

### POST creazione (BE-2.1 / BE-4.2)

```http
POST /api/v1/ricevute
Content-Type: application/json
Authorization: Bearer <JWT>

{
  "id_order": 45001,
  "data_emissione": "2026-07-08T14:30:00"
}
```

| Campo | Obbligatorio | Note |
|-------|--------------|------|
| `id_order` | sì | PK ordine gestionale |
| `data_emissione` | no | ISO 8601 data+ora (Europe/Rome); default: adesso. Accetta anche `"2026-07-08"` (solo data → ora corrente su quel giorno) |

**Response 201:** `RicevutaDetail` completa con `pdf_path` popolato.

**Errori business (400):**
- ordine già fatturato
- ricevuta emessa già presente per l'ordine
- ordine senza `payment_date` / non pagato

---

### PUT aggiornamento (BE-2.4)

```http
PUT /api/v1/ricevute/{id_ricevuta}
{ "data_emissione": "2026-07-10T09:15:00" }
```

Rigenera il PDF. Bloccato solo se ricevuta non emessa (`stato !== 'emessa'`).  
Se `is_modifiable === false` (ordine in Spedizione Confermata), il BE **non** blocca: mostrare warning di conferma lato FE.

---

### DELETE — cancellazione definitiva (BE-2.4)

```http
DELETE /api/v1/ricevute/{id_ricevuta}
```

**204 No Content** — elimina record DB e file PDF su disco. Dopo la cancellazione l'ordine può ricevere una nuova ricevuta.

Se `is_modifiable === false`, il BE **non** blocca: mostrare warning di conferma lato FE.

> **Nota:** eventuali ricevute legacy con `stato=annullata` restano in DB finché non eliminate manualmente; il DELETE non imposta più `annullata`.

---

### PDF (BE-2.3)

```http
GET  /api/v1/ricevute/{id_ricevuta}/pdf   # download (rigenera se mancante)
GET  /api/v1/ricevute/{id_ricevuta}/pdf?regenerate=1   # forza rigenerazione template
POST /api/v1/ricevute/{id_ricevuta}/pdf   # rigenera e restituisce blob
```

Response: `application/pdf`, `Content-Disposition: inline`.

> **Importante:** il GET senza `regenerate` restituisce il file già salvato in `media/ricevute/`. Dopo un aggiornamento del template PDF, usare `?regenerate=1` o `POST .../pdf` (e riavviare l'API se il server non ha ricaricato il codice).

**Layout PDF (2026-07-08):** stile elettronew B/N (come stampa ordine legacy), non layout fattura SDI. Sezioni: logo + anagrafica società, `RICEVUTA n° {numero}/{anno} la {data_emissione gg/mm/aaaa hh:mm}`, En-tête / indirizzo consegna (label FR se `country.iso_code=FR`), riga `ORDINE n° …`, tabella righe, totali a destra. Le note ordine (`general_note`) non compaiono nel PDF (solo uso interno). Implementazione: `src/services/pdf/ricevuta_pdf_layout.py`.

---

### Export CSV/Excel (BE-2.5)

**Singola ricevuta** (header + `order_details`):

```http
GET /api/v1/ricevute/{id_ricevuta}/export?fmt=csv
GET /api/v1/ricevute/{id_ricevuta}/export?fmt=xlsx
```

Filename: `Ricevuta-{numero}-{anno}.csv|xlsx`. CSV con separatore `;` e BOM UTF-8 (Excel).

**Massivo** (stessi filtri della lista, max 5000 righe):

```http
GET /api/v1/ricevute/export?fmt=xlsx&data_emissione_from=2026-01-01&data_emissione_to=2026-12-31
```

Response: `Content-Disposition: attachment`. XLSX singola: fogli `Ricevuta` + `order_details`.

```typescript
downloadRicevutaExport(idRicevuta: number, fmt: 'csv' | 'xlsx' = 'csv'): Observable<Blob> {
  return this.http.get(
    `${this.apiBase}/api/v1/ricevute/${idRicevuta}/export`,
    { params: { fmt }, responseType: 'blob' }
  );
}
```

Permesso: `fiscal_documents:read`.

---

### `is_modifiable`

Solo a livello root (`RicevutaDetail.is_modifiable`). Per link ordine usare `order.id_order`.

| Valore | Significato FE |
|--------|----------------|
| `true` | Ordine **non** in Spedizione Confermata |
| `false` | Ordine in **Spedizione Confermata** (`id_order_state === 4`) → eventuale **warning** FE su POST/PUT/DELETE (BE non blocca) |

**Nota FE:** con `is_modifiable === false` mostrare dialog di conferma prima di PUT/DELETE; non disabilitare i bottoni solo per questo flag (salvo policy UX interna).

### Display numero documento

Mostrare come **`{numero}/{anno}`** (es. `7/2026`).

### Righe prodotto

In dettaglio, `order_details[]` proviene da `order_details` dell’ordine (escluse righe con `id_order_document`) **+ eventuale riga spedizione** sintetica (`is_shipping: true`, `id_order_detail: 0`, `product_name: "Spedizione"`). Totali ordine in `order.total_price_with_tax` includono già spedizione; campi dedicati: `order.shipping_total_price_with_tax` / `shipping_total_price_net`.

### PDF (step 2 — non ancora disponibile)

Quando arriverà BE-2.3, i campi utili saranno:

- `pdf_path` — path relativo o URL interno
- `pdf_generated_at` — timestamp ultima generazione
- Endpoint atteso: `POST /api/v1/ricevute/{id}/pdf` o blob GET dedicato

Per ora: mostrare placeholder «PDF non ancora generato» se `pdf_path` è `null`.

---

## TypeScript — tipi consigliati

Copiare in `src/app/core/models/ricevuta.model.ts` (path adattabile):

```typescript
export type RicevutaStato = 'emessa' | 'annullata';

export interface RicevutaCustomerSummary {
  id_customer: number | null;
  id_origin: number | null;
  id_lang: number | null;
  id_store: number | null;
  firstname: string | null;
  lastname: string | null;
  email: string | null;
  date_add: string | null; // ISO datetime
}

export interface RicevutaCountry {
  name: string | null;
  iso_code: string | null;
}

export interface RicevutaAddress {
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
  country: RicevutaCountry | null;
}

export interface RicevutaOrderDetail {
  id_order_detail: number;
  id_product: number | null;
  product_name: string | null;
  product_reference: string | null;
  product_qty: number;
  id_tax: number | null;
  unit_price_net: number | null;
  unit_price_with_tax: number | null;
  total_price_net: number | null;
  total_price_with_tax: number | null;
  reduction_percent: number | null;
  reduction_amount: number | null;
  /** Riga spedizione sintetica (`id_order_detail=0`) — non sommare due volte con order.shipping_* */
  is_shipping: boolean;
}

export interface RicevutaOrderSummary {
  id_order: number;
  reference: string | null;
  id_order_state: number;
  is_payed: boolean;
  payment_date: string | null; // YYYY-MM-DD
  total_price_with_tax: number;
  total_price_net: number | null;
  products_total_price_with_tax: number | null;
  products_total_price_net: number | null;
  shipping_total_price_with_tax: number | null;
  shipping_total_price_net: number | null;
  total_discounts: number | null;
  general_note: string | null;
}

export interface RicevutaListItem {
  id_ricevuta: number;
  numero: number;
  anno: number;
  id_order: number;
  data_incasso: string; // YYYY-MM-DD
  data_emissione: string; // ISO 8601 datetime (es. 2026-06-05T10:30:00)
  stato: RicevutaStato;
  pdf_path: string | null;
  pdf_generated_at: string | null;
  customer: RicevutaCustomerSummary | null;
  order_reference: string | null;
  order_total_with_tax: number | null;
}

export interface RicevutaListResponse {
  ricevute: RicevutaListItem[];
  total: number;
  page: number;
  limit: number;
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
  customer: RicevutaCustomerSummary | null;
  order: RicevutaOrderSummary | null;
  address_delivery: RicevutaAddress | null;
  address_invoice: RicevutaAddress | null;
  order_details: RicevutaOrderDetail[];
}

export interface RicevutaListFilters {
  id_order?: number;
  id_customer?: number;
  stato?: RicevutaStato;
  data_emissione_from?: string;
  data_emissione_to?: string;
  page?: number;
  limit?: number;
}
```

---

## Esempio response — lista

```json
{
  "ricevute": [
    {
      "id_ricevuta": 12,
      "numero": 7,
      "anno": 2026,
      "id_order": 45001,
      "data_incasso": "2026-06-01",
      "data_emissione": "2026-06-05",
      "stato": "emessa",
      "pdf_path": null,
      "pdf_generated_at": null,
      "customer": {
        "id_customer": 880,
        "firstname": "Luigi",
        "lastname": "Verdi",
        "email": "luigi@example.com"
      },
      "order_reference": "ORD-SVC-001",
      "order_total_with_tax": 244.0
    }
  ],
  "total": 1,
  "page": 1,
  "limit": 10
}
```

---

## Esempio response — dettaglio (estratti)

```json
{
  "id_ricevuta": 12,
  "numero": 7,
  "anno": 2026,
  "stato": "emessa",
  "data_incasso": "2026-06-01",
  "data_emissione": "2026-06-05",
  "is_modifiable": true,
  "customer": {
    "id_customer": 880,
    "firstname": "Luigi",
    "lastname": "Verdi",
    "email": "luigi@example.com"
  },
  "order": {
    "id_order": 45001,
    "reference": "ORD-SVC-001",
    "id_order_state": 1,
    "is_payed": true,
    "payment_date": "2026-06-01",
    "total_price_with_tax": 244.0
  },
  "address_delivery": {
    "id_address": 12001,
    "company": "Acme GmbH",
    "firstname": "Luigi",
    "lastname": "Verdi",
    "address1": "Hauptstr. 1",
    "city": "Berlin",
    "postcode": "10115",
    "country": { "iso_code": "DE", "name": "Germania" }
  },
  "address_invoice": {
    "id_address": 12001,
    "company": "Acme GmbH",
    "firstname": "Luigi",
    "lastname": "Verdi",
    "address1": "Hauptstr. 1",
    "city": "Berlin",
    "postcode": "10115",
    "country": { "iso_code": "DE", "name": "Germania" }
  },
  "order_details": [
    {
      "id_order_detail": 901,
      "product_name": "Articolo test",
      "product_reference": "REF-1",
      "product_qty": 2,
      "id_tax": 1,
      "total_price_with_tax": 244.0
    }
  ]
}
```

---

## Service HTTP — pattern consigliato

```typescript
listRicevute(filters: RicevutaListFilters): Observable<RicevutaListResponse> {
  const params = new HttpParams({ fromObject: cleanUndefined(filters) });
  return this.http.get<RicevutaListResponse>(
    `${this.apiBase}/api/v1/ricevute`,
    { params }
  );
}

getRicevuta(idRicevuta: number): Observable<RicevutaDetail> {
  return this.http.get<RicevutaDetail>(
    `${this.apiBase}/api/v1/ricevute/${idRicevuta}`
  );
}
```

Helper `cleanUndefined`: rimuovere chiavi `undefined`/`null` prima di costruire `HttpParams`.

---

## Task FE suggeriti (step 1 — parallelo al BE)

| # | Task | Dipendenze BE |
|---|------|----------------|
| 1 | Modelli TS + `ricevute.service.ts` | ✅ GET pronti |
| 2 | Route `/fatturazione/ricevute` (o sezione equivalente) | ✅ |
| 3 | Tabella lista con filtri stato + range date emissione | ✅ |
| 4 | Pagina/modale dettaglio con header, cliente, `order_details`, totali ordine | ✅ |
| 5 | Badge stato `emessa` / `annullata` | ✅ |
| 6 | Warning Modifica/Elimina se `!is_modifiable` (azioni **non** bloccate dal BE) | ✅ flag pronto |
| 7 | Link ordine → modale ordine esistente (`id_order`) | ✅ |
| 8 | Bottone «Genera ricevuta» da ordine | ⏳ attendere BE-2.1 POST |
| 9 | Anteprima/scarica PDF | ⏳ attendere BE-2.3 |

---

## Stati ordine (riferimento)

| `id_order_state` | Nome (seed BE) |
|------------------|----------------|
| 1 | In Preparazione |
| 2 | Pronti Per La Spedizione |
| 3 | Spediti |
| **4** | **Spedizione Confermata** → `is_modifiable: false` (warning FE opzionale su POST/PUT/DELETE) |
| 5 | Annullati |
| 6 | In Attesa |

Il FE può anche riusare `order.id_order_state` già esposto nel dettaglio ordine esistente.

---

## Prossimo contratto BE (preview — non implementato)

Per allineamento anticipato:

```http
POST /api/v1/ricevute
Content-Type: application/json

{
  "id_order": 45001,
  "data_emissione": "2026-07-08"
}
```

Response attesa: `RicevutaDetail` completa (con PDF path quando BE-2.3 sarà attivo).

---

## Riferimento codice BE

| Componente | Path |
|------------|------|
| Router | `src/routers/ricevute.py` |
| Schemas | `src/schemas/ricevuta_schema.py` |
| Service | `src/services/routers/ricevuta_service.py` |
| Model | `src/models/ricevuta.py` |
