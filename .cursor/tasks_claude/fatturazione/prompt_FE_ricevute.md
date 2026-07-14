# Prompt sessione FE — Ricevute estero (allineamento BE 2026-07-08)

Copia tutto il contenuto **sotto la riga `---`** e incollalo in una nuova chat Cursor sul **repository del gestionale Angular**.

**Prerequisito BE (obbligatorio):** su ogni ambiente (dev/staging/prod) deve esistere la tabella `ricevute`.  
Se i GET rispondono **500** con errore SQL *table doesn't exist*, il BE non ha ancora applicato la migration:
Se i GET rispondono **500** con errore SQL *table doesn't exist*, il BE non ha ancora applicato la migration:
Se i GET rispondono **500** con errore SQL *table doesn't exist*, il BE non ha ancora applicato la migration:

```bash
# Dal repo ECommerceManagerAPI, con venv attivo e .env configurato
python scripts/migrations/create_ricevute_table.py
# oppure: alembic revision --autogenerate -m "create ricevute table" && alembic upgrade head
```

Handoff dettagliato: `docs/FE_HANDOFF_RICEVUTE.md` (repo BE).  
Task BE: `.cursor/tasks_claude/fatturazione/TASKS_BE_ricevute.md`

---

## Contesto

Le **ricevute** sono documenti fiscali **interni** (no SDI) per clienti esteri privati senza P.IVA.

Dati ordine/cliente/righe sempre **live** (nessuna tabella righe o snapshot cliente).

### Stato BE consegnato (usa questo come fonte di verità)

| Step | Stato | Endpoint |
|------|-------|----------|
| BE-1 Schema DB | ✅ | tabella `ricevute` |
| BE-2.2 GET lista/dettaglio | ✅ | `GET /ricevute`, `GET /ricevute/{id}` |
| BE-2.1 POST creazione | ✅ | `POST /ricevute` |
| BE-2.3 PDF | ✅ | `GET /ricevute/{id}/pdf`, `POST /ricevute/{id}/pdf` |
| BE-2.4 PUT / annulla | ✅ | `PUT /ricevute/{id}`, `DELETE /ricevute/{id}` |
| BE-4.2 da modale ordine | ✅ | stesso `POST /ricevute` |
| BE-3 Corrispettivi | ⏳ | non toccare UI corrispettivi ancora |
| BE-2.5 Export / BE-2.6 Email | ⏳ | non implementare |

---

## Autenticazione e permessi RBAC

Base: `{API_BASE}/api/v1/ricevute`  
Header: `Authorization: Bearer <JWT>`

| Azione | Permesso |
|--------|----------|
| Lista, dettaglio, download PDF | `fiscal_documents:read` |
| Crea ricevuta | `fiscal_documents:create` |
| Modifica data emissione, rigenera PDF | `fiscal_documents:update` |
| Annulla (soft delete) | `fiscal_documents:delete` |

Stesso modulo dei **Corrispettivi** / Fatture.

---

## API — contratto completo

### 1) Lista (già integrata — verifica shape response)

```http
GET /api/v1/ricevute?id_order=&id_customer=&stato=&data_emissione_from=&data_emissione_to=&page=1&limit=10
```

Response:

```json
{
  "ricevute": [ { "id_ricevuta": 1, "numero": 7, "anno": 2026, "...": "..." } ],
  "total": 0,
  "page": 1,
  "limit": 10
}
```

Lista **vuota** (`total: 0`) = OK, non è un errore.  
Errore **500** = quasi sempre tabella DB mancante lato BE (vedi prerequisito).

---

### 2) Dettaglio

```http
GET /api/v1/ricevute/{id_ricevuta}
```

Include: header ricevuta, `customer`, `order`, `address_delivery` + `address_invoice` (nullable), `order_details[]` (live da ordine), `is_modifiable`.

**Contratto v2:** niente `id_order`/`id_customer`/`pdf_hash` in root; niente `customer` annidato negli indirizzi; sempre `address_delivery` e `address_invoice`.

---

### 3) Crea ricevuta (modale ordine — BE-2.1 / BE-4.2)

```http
POST /api/v1/ricevute
Content-Type: application/json

{
  "id_order": 45001,
  "data_emissione": "2026-07-08"
}
```

| Campo | Obbligatorio | Note |
|-------|--------------|------|
| `id_order` | sì | PK gestionale ordine |
| `data_emissione` | no | default: oggi (Europe/Rome) |

**Response 201:** stesso shape di `RicevutaDetail`, con `pdf_path` e `pdf_generated_at` già popolati (PDF generato in creazione).

**Errori 400 (business):**
- ordine in **Spedizione Confermata** (`id_order_state === 4`)
- ordine **già fatturato**
- **ricevuta emessa già esistente** per quell'ordine
- ordine senza data pagamento / non pagato

Dopo POST riuscito: aprire dettaglio o anteprima PDF senza chiamate extra.

---

### 4) Modifica data emissione

```http
PUT /api/v1/ricevute/{id_ricevuta}
{ "data_emissione": "2026-07-10" }
```

Rigenera il PDF. Bloccato se ordine spedito o ricevuta già annullata.

---

### 5) Annulla (soft delete)

```http
DELETE /api/v1/ricevute/{id_ricevuta}
```

Imposta `stato: "annullata"`, `annullata_at`, `annullata_da_user_id`.  
Response: `RicevutaDetail` aggiornato. **Nessuna cancellazione fisica.**

---

### 6) PDF

```http
GET  /api/v1/ricevute/{id_ricevuta}/pdf   # download inline (rigenera se file assente)
POST /api/v1/ricevute/{id_ricevuta}/pdf   # rigenera e restituisce blob
```

- Response: `application/pdf`
- Pattern identico a DDT / ordine / preventivo: `responseType: 'blob'` + `window.open`

```typescript
downloadRicevutaPdf(idRicevuta: number): Observable<Blob> {
  return this.http.get(
    `${this.apiBase}/api/v1/ricevute/${idRicevuta}/pdf`,
    { responseType: 'blob' }
  );
}
```

---

### 7) Export CSV/Excel (BE-2.5)

```http
GET /api/v1/ricevute/{id_ricevuta}/export?fmt=csv|xlsx
GET /api/v1/ricevute/export?fmt=csv|xlsx&data_emissione_from=&data_emissione_to=
```

- Singola: righe prodotto + metadati; filename `Ricevuta-{numero}-{anno}.*`
- Massivo: riepilogo lista (max 5000); stessi filtri di GET lista
- `responseType: 'blob'` + download con `Content-Disposition`

---

## Regole UI — `is_modifiable`

Solo su root (`RicevutaDetail.is_modifiable`). Per navigazione ordine: `order.id_order`.

| Valore | Significato |
|--------|-------------|
| `true` | Ordine non in Spedizione Confermata → abilita Modifica / Annulla |
| `false` | `id_order_state === 4` → disabilita azioni + tooltip |

**Nota:** su ricevuta **annullata** le azioni vanno disabilitate indipendentemente da `is_modifiable` (`stato === 'annullata'`).

Display numero documento: **`{numero}/{anno}`** (es. `7/2026`).

Verifica ricevuta esistente per ordine (modale ordine):

```http
GET /api/v1/ricevute?id_order={id_order}&stato=emessa
```

Se `total > 0` → mostra link a dettaglio invece del bottone «Genera».

---

## TypeScript — modelli (allineati al BE)

File: `src/app/core/models/ricevuta.model.ts`

```typescript
export type RicevutaStato = 'emessa' | 'annullata';

export interface RicevutaCreateRequest {
  id_order: number;
  data_emissione?: string; // YYYY-MM-DD
}

export interface RicevutaUpdateRequest {
  data_emissione: string; // YYYY-MM-DD
}

export interface RicevutaCustomerSummary {
  id_customer: number | null;
  firstname: string | null;
  lastname: string | null;
  email: string | null;
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
}

export interface RicevutaOrderSummary {
  id_order: number;
  reference: string | null;
  id_order_state: number;
  is_payed: boolean;
  payment_date: string | null;
  total_price_with_tax: number;
  total_price_net: number | null;
  products_total_price_with_tax: number | null;
  products_total_price_net: number | null;
  total_discounts: number | null;
  general_note: string | null;
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

## Service HTTP — metodi da implementare/estendere

File: `src/app/core/services/ricevute.service.ts`

```typescript
listRicevute(filters: RicevutaListFilters): Observable<RicevutaListResponse> { /* già fatto */ }
getRicevuta(id: number): Observable<RicevutaDetail> { /* già fatto */ }

createRicevuta(body: RicevutaCreateRequest): Observable<RicevutaDetail> {
  return this.http.post<RicevutaDetail>(`${this.apiBase}/api/v1/ricevute`, body);
}

updateRicevuta(id: number, body: RicevutaUpdateRequest): Observable<RicevutaDetail> {
  return this.http.put<RicevutaDetail>(`${this.apiBase}/api/v1/ricevute/${id}`, body);
}

annullaRicevuta(id: number): Observable<RicevutaDetail> {
  return this.http.delete<RicevutaDetail>(`${this.apiBase}/api/v1/ricevute/${id}`);
}

downloadRicevutaPdf(id: number): Observable<Blob> {
  return this.http.get(`${this.apiBase}/api/v1/ricevute/${id}/pdf`, { responseType: 'blob' });
}

regenerateRicevutaPdf(id: number): Observable<Blob> {
  return this.http.post(`${this.apiBase}/api/v1/ricevute/${id}/pdf`, null, { responseType: 'blob' });
}
```

---

## Task FE — checklist aggiornata

### Già fatto (step 1) — verificare
- [ ] `listRicevute` + `getRicevuta`
- [ ] Lista con filtri e paginazione
- [ ] Dettaglio con `order_details` live (stesso naming degli ordini)

### Da completare ora (step 2)
- [ ] `createRicevuta` — bottone **Genera ricevuta** in modale ordine
- [ ] Dopo POST → navigazione dettaglio o apertura PDF
- [ ] `downloadRicevutaPdf` — viewer/stampa (pattern DDT)
- [ ] `updateRicevuta` — modifica data emissione (datepicker + conferma)
- [ ] `annullaRicevuta` — conferma Swal/dialog
- [ ] Disabilitare Modifica/Annulla/Genera se `!is_modifiable` o `stato === 'annullata'`
- [ ] Gestione errori 400 business (messaggio da `detail` / `message` interceptor)
- [ ] In modale ordine: `GET ?id_order=X&stato=emessa` per evitare doppia emissione

### Non fare ancora
- ❌ Export CSV/Excel (BE-2.5)
- ❌ Invio email (BE-2.6)
- ❌ Modifiche UI corrispettivi (BE-3)

---

## Stati ordine (riferimento)

| `id_order_state` | Nome |
|------------------|------|
| 4 | Spedizione Confermata → **blocca** creazione/modifica/annullo ricevuta |

---

## Test manuali

1. **Lista vuota** → tabella empty state, nessun crash (non confondere con 500).
2. **Genera ricevuta** da ordine pagato estero → 201, PDF apribile.
3. **Doppio click Genera** → 400 «ricevuta già esistente».
4. **Ordine spedito** (`id_order_state=4`) → Genera disabilitato o 400.
5. **Annulla** → badge `annullata`, bottoni disabilitati.
6. **PDF** → blob in nuova tab; fallback download se popup blocker.

---

## Definition of done

- [ ] Tutti i metodi service sopra
- [ ] Flusso completo ordine → ricevuta → PDF
- [ ] Modifica data emissione + annullo funzionanti
- [ ] `is_modifiable` + `stato` rispettati in UI
- [ ] Errori 400/403/500 gestiti (500 migration = segnalare a BE)

---

## Riferimento BE (solo lettura)

Repo: **ECommerceManagerAPI**  
Router: `src/routers/ricevute.py`  
Schemas: `src/schemas/ricevuta_schema.py`  
Migration: `scripts/migrations/create_ricevute_table.py`
