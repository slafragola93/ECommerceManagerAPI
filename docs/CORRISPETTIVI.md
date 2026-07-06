# Corrispettivi — Reference API (Backend)

Documento di riferimento per integrazione **Frontend (Angular/NgRx)** e QA.

**Base URL:** `/api/v1/corrispettivi`  
**Autenticazione:** Bearer JWT (header `Authorization: Bearer <token>`)  
**Permesso richiesto:** modulo `fiscal_documents`, azione `read` (su tutti gli endpoint, export incluso)  
**Swagger:** `http://localhost:8000/docs` → tag **Corrispettivi**

---

## 1. Panoramica architetturale

I corrispettivi sono un **report fiscale interno** (no SDI, no servizi esterni). I dati **non sono persistiti** in tabella dedicata: ogni chiamata ricalcola aggregati live da:

| Fonte | Uso |
|---|---|
| `orders` | Vendite (ordini non fatturati) |
| `order_details` | Imponibile prodotti per aliquota (`id_tax`) |
| `shipments` | Imponibile spedizione per aliquota |
| `fiscal_documents` + `fiscal_document_details` | Resi su ordini non fatturati |

### Regole di business

| Regola | Dettaglio |
|---|---|
| Perimetro vendite | Ordini **senza** `FiscalDocument` con `document_type = "invoice"` |
| Data vendite | `Order.date_add` (giorno in timezone `Europe/Rome`) |
| Data resi | `FiscalDocument.date_add` del documento reso |
| Perimetro resi | Solo resi collegati a ordini non fatturati |
| Giorni in response | **Solo giorni con almeno un movimento** (vendita e/o reso) |
| Export | **Un solo mese** per richiesta |
| Note di credito | Fuori scope |

### Retroattività

- È possibile consultare **mesi passati** (`year` + `month` qualsiasi).
- I totali **possono cambiare nel tempo** se un ordine viene fatturato dopo la data ordine (query live, nessuno snapshot congelato).

---

## 2. Organizzazione endpoint

Due endpoint **GET** per consultazione (viste diverse sugli stessi dati) + un **POST** per export file.

```
┌─────────────────────────────────────────────────────────────────┐
│  Filtri comuni: year, month, id_platform, id_store,             │
│                 delivery_country_iso, day                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
       GET /riepilogo                  GET /
       (matrice UI + columns)    (totali giornalieri)
              │                             │
              └──────────────┬──────────────┘
                             │
                    POST /export
                    (ZIP Registri.zip)
```

| Endpoint | Quando usarlo (FE) |
|---|---|
| `GET /riepilogo` | **Schermata principale** — tabella giorni × aliquote; include `columns` (header aliquote) |
| `GET /` | Opzionale — card/summary con totali giornalieri, split prodotti/spedizione, conteggi ordini/resi |
| `POST /export` | Pulsante **Esporta** → download `Registri.zip` |

---

## 3. Filtri

Parametri identici su tutti i GET (query string) e nel body export (`filters`).

| Parametro | Tipo | Obbligatorio | Descrizione |
|---|---|---|---|
| `year` | int | Sì | Anno (2000–2100) |
| `month` | int | Sì | Mese (1–12) |
| `id_platform` | int | No | Canale → `Order.id_platform` |
| `id_store` | int | No | Conto/store → `Order.id_store` |
| `delivery_country_iso` | string | No | Paese consegna ISO (es. `IT`, `DE`) — filtra matrice/export per paese |
| `day` | int | No | Giorno del mese (1–31) — restringe a un solo giorno |

**Mapping UI legacy → API**

| Controllo UI legacy | Parametro API |
|---|---|
| Anno (dropdown) | `year` |
| Checkbox mese (uno solo per richiesta) | `month` |
| Giorno opzionale | `day` |
| Tutti i canali | omit `id_platform` |
| Tutti i conti | omit `id_store` |
| Tutte le nazioni | omit `delivery_country_iso` |
| Corrispettivi + calcolo per data documento | implicito (`calculation_mode: order_document_date`) |

---

## 4. Endpoint — dettaglio e formati risposta

### 4.1 `GET /api/v1/corrispettivi/riepilogo`

**Scopo:** matrice principale per la UI — righe = giorni, colonne = aliquote IVA.

**Request esempio:**
```http
GET /api/v1/corrispettivi/riepilogo?year=2026&month=5&id_store=1
Authorization: Bearer <token>
```

**Response `200` — schema:**

```typescript
interface CorrispettivoRiepilogoResponse {
  year: number;
  month: number;
  calculation_mode: "order_document_date";  // fisso
  timezone: "Europe/Rome";                // fisso
  delivery_country_iso: string | null;    // valorizzato se filtro paese attivo
  columns: CorrispettivoTaxColumn[];
  rows: CorrispettivoRiepilogoRow[];
  month_totals: CorrispettivoAmount;
}

interface CorrispettivoTaxColumn {
  id_tax: number;
  label: string;           // es. "22", "0", "SPF", "17L"
  percentage: number | null;
}

interface CorrispettivoAmount {
  sales_net: number;       // imponibile vendite (2 decimali)
  returns_net: number;     // imponibile resi
  net: number;             // sales_net - returns_net
}

interface CorrispettivoRiepilogoRow {
  day: number;             // 1-31
  date: string;            // ISO date "2026-05-15"
  cells: Record<string, CorrispettivoAmount>;  // chiave = id_tax come stringa ("1", "9")
  row_net: CorrispettivoAmount;               // totale riga (somma aliquote prodotti)
  shipping: {
    sales_net: number;
    returns_net: number;
  };
}
```

**Response JSON esempio:**
```json
{
  "year": 2026,
  "month": 5,
  "calculation_mode": "order_document_date",
  "timezone": "Europe/Rome",
  "delivery_country_iso": null,
  "columns": [
    { "id_tax": 1, "label": "22", "percentage": 22.0 },
    { "id_tax": 9, "label": "0", "percentage": 0.0 }
  ],
  "rows": [
    {
      "day": 15,
      "date": "2026-05-15",
      "cells": {
        "1": { "sales_net": 901.64, "returns_net": 10.0, "net": 891.64 },
        "9": { "sales_net": 120.0, "returns_net": 0.0, "net": 120.0 }
      },
      "row_net": { "sales_net": 1021.64, "returns_net": 10.0, "net": 1011.64 },
      "shipping": { "sales_net": 122.95, "returns_net": 0.0 }
    }
  ],
  "month_totals": { "sales_net": 1021.64, "returns_net": 10.0, "net": 1011.64 }
}
```

**Note rendering UI:**

- `columns` definisce l’ordine delle colonne aliquota.
- Per ogni riga, usare `cells[String(column.id_tax)]`; se assente → `{ sales_net: 0, returns_net: 0, net: 0 }`.
- **Vendite** → colore verde (legacy); **resi** → rosso; mostrare `sales_net` e `returns_net` **separati** (non stringhe comma-separated).
- Colonna **Netto** a destra → `row_net.net` (o breakdown `row_net.sales_net` / `row_net.returns_net`).
- Riga **Spedizione** opzionale sotto ogni giorno → `shipping`.
- `month_totals` → riga totali in fondo tabella.

---

### 4.2 `GET /api/v1/corrispettivi/`

**Scopo:** vista compatta per totali giornalieri (card, riepilogo numerico) con importi **con IVA** e **netti**, split prodotti/spedizione.

**Request:**
```http
GET /api/v1/corrispettivi/?year=2026&month=5
```

**Response `200` — schema:**

```typescript
interface CorrispettivoListResponse {
  year: number;
  month: number;
  timezone: "Europe/Rome";
  days: CorrispettivoDaySummary[];
  month_totals: CorrispettivoSplitTotals;
}

interface CorrispettivoSplitTotals {
  total_with_tax: number;
  total_net: number;
  products_with_tax: number;
  products_net: number;
  shipping_with_tax: number;
  shipping_net: number;
  order_count: number;    // solo in blocco "sales"
  return_count: number;   // solo in blocco "returns"
}

interface CorrispettivoDaySummary {
  date: string;           // ISO "2026-05-15"
  sales: CorrispettivoSplitTotals;
  returns: CorrispettivoSplitTotals;
  net: CorrispettivoSplitTotals;   // sales - returns per campo
}
```

**Response JSON esempio:**
```json
{
  "year": 2026,
  "month": 5,
  "timezone": "Europe/Rome",
  "days": [
    {
      "date": "2026-05-15",
      "sales": {
        "total_with_tax": 1244.59,
        "total_net": 1021.64,
        "products_with_tax": 1100.0,
        "products_net": 901.64,
        "shipping_with_tax": 144.59,
        "shipping_net": 122.95,
        "order_count": 12,
        "return_count": 0
      },
      "returns": {
        "total_with_tax": 12.2,
        "total_net": 10.0,
        "products_with_tax": 12.2,
        "products_net": 10.0,
        "shipping_with_tax": 0.0,
        "shipping_net": 0.0,
        "order_count": 0,
        "return_count": 2
      },
      "net": {
        "total_with_tax": 1232.39,
        "total_net": 1011.64,
        "products_with_tax": 1087.8,
        "products_net": 891.64,
        "shipping_with_tax": 144.59,
        "shipping_net": 122.95,
        "order_count": 0,
        "return_count": 0
      }
    }
  ],
  "month_totals": { "...": "somma dei net per tutti i giorni" }
}
```

**Differenza vs `/riepilogo`:**

| Aspetto | `/riepilogo` | `/` |
|---|---|---|
| Granularità | Per **aliquota IVA** | Per **giorno** (totali) |
| Importi | Imponibile (`*_net`) per cella | Con IVA + netto + split prodotti/spedizione |
| Uso UI | Tabella matriciale | Summary / KPI |

---

### 4.3 `POST /api/v1/corrispettivi/export`

**Scopo:** genera ZIP **Registri.zip** con Excel per paese (equivalente export legacy).

**Request:**
```http
POST /api/v1/corrispettivi/export
Content-Type: application/json
Authorization: Bearer <token>

{
  "year": 2026,
  "month": 5,
  "filters": {
    "id_platform": null,
    "id_store": 1,
    "delivery_country_iso": null,
    "day": null
  }
}
```

| Campo body | Tipo | Obbligatorio |
|---|---|---|
| `year` | int | Sì |
| `month` | int | Sì |
| `filters` | object | No (stessi campi dei filtri GET) |

**Response `200`:**

| Header | Valore |
|---|---|
| `Content-Type` | `application/zip` |
| `Content-Disposition` | `attachment; filename="Registri.zip"` |

**Contenuto ZIP:**

| File | Descrizione |
|---|---|
| `registro.xlsx` | Consolidato tutti i paesi |
| `registro_IT.xlsx` | Solo consegne IT |
| `registro_DE.xlsx` | Solo consegne DE |
| … | Un file per ogni ISO con movimenti nel mese |

**Struttura Excel (ogni file):**

- Header: `Giorno`, `Data`, per ogni aliquota `{label} Vendite` + `{label} Resi`, poi `Netto Vendite`, `Netto Resi`, `Netto`, `Sped. Vendite`, `Sped. Resi`
- Righe: solo giorni con movimento
- Ultima riga: totali mese

**FE — download blob:**
```typescript
this.http.post(`${baseUrl}/api/v1/corrispettivi/export`, body, {
  responseType: 'blob',
  headers: { Authorization: `Bearer ${token}` }
}).subscribe(blob => {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'Registri.zip';
  a.click();
  window.URL.revokeObjectURL(url);
});
```

---

## 5. Errori HTTP e troubleshooting

| Codice | Caso |
|---|---|
| `401` | Token assente/non valido — vedi sotto |
| `403` | Permesso `fiscal_documents:read` mancante |
| `422` | Parametri non validi (`year`, `month`, `day` fuori range) |
| `500` | Errore interno aggregazione/export |

Formato errori standard API (vedi `DOCUMENTAZIONE.md`).

### 401 su `/riepilogo` — diagnosi

Il messaggio **`Not authenticated`** indica che **manca l'header** `Authorization: Bearer <token>`, non un bug del calcolo corrispettivi.

| Messaggio API | Significato |
|---|---|
| `Not authenticated` | Header `Authorization` assente |
| `Token non valido o scaduto` | Header presente ma JWT scaduto/errato |
| `403` + `PERMISSION_DENIED` | Token OK, permesso `fiscal_documents:read` mancante |

Dalla risposta 401 il backend include anche:

```json
{
  "details": {
    "authorization_header_present": false,
    "hint": "Inviare header Authorization: Bearer <access_token> su ogni richiesta API"
  }
}
```

Nei log server compare `authorization_header_present: false` sulle richieste 401.

**Checklist FE (Angular):**

1. Usare **sempre** `HttpClient` con l'interceptor JWT (no `fetch`/`XMLHttpRequest` diretti).
2. URL corretto: `GET /api/v1/corrispettivi/riepilogo?year=&month=` (accettato anche `/riepilogo/`).
3. Summary giornaliero: `GET /api/v1/corrispettivi/?year=&month=` — alias legacy `GET /summary` mappato su `/`.
4. In DevTools → Network, sulla richiesta fallita verificare che l'header `Authorization` sia presente.
5. Se altre chiamate (es. `/init/`) sono 200 ma `/riepilogo` è 401, spesso c'è una **seconda chiamata** duplicata senza interceptor (effect NgRx, servizio parallelo, retry manuale).

**Nota:** la stessa URL può restituire 200 e 401 a pochi secondi di distanza se una richiesta include il token e l'altra no.

---

## 6. Flusso UI consigliato (FE)

```
1. Utente seleziona anno + mese (+ filtri opzionali)
2. Click "Genera"
   → dispatch loadCorrispettiviRiepilogo({ year, month, filters })
   → GET /riepilogo
   → (opzionale parallelo) GET / per summary card
3. Render tabella da response.columns + response.rows
4. Click "Esporta"
   → POST /export con stessi year/month/filters
   → download Registri.zip
```

**Un solo mese per richiesta:** se l’UI ha checkbox multipli mesi, il FE deve iterare o forzare selezione singola prima di Genera/Esporta.

---

## 7. Modelli TypeScript (copia-incolla FE)

File suggerito: `src/app/features/corrispettivi/models/corrispettivo.models.ts`

```typescript
export interface CorrispettivoFilters {
  id_platform?: number;
  id_store?: number;
  delivery_country_iso?: string;
  day?: number;
}

export interface CorrispettivoQueryParams extends CorrispettivoFilters {
  year: number;
  month: number;
}

export interface CorrispettivoAmount {
  sales_net: number;
  returns_net: number;
  net: number;
}

export interface CorrispettivoTaxColumn {
  id_tax: number;
  label: string;
  percentage: number | null;
}

export interface CorrispettivoShippingDay {
  sales_net: number;
  returns_net: number;
}

export interface CorrispettivoRiepilogoRow {
  day: number;
  date: string;
  cells: Record<string, CorrispettivoAmount>;
  row_net: CorrispettivoAmount;
  shipping: CorrispettivoShippingDay;
}

export interface CorrispettivoRiepilogoResponse {
  year: number;
  month: number;
  calculation_mode: string;
  timezone: string;
  delivery_country_iso: string | null;
  columns: CorrispettivoTaxColumn[];
  rows: CorrispettivoRiepilogoRow[];
  month_totals: CorrispettivoAmount;
}

export interface CorrispettivoSplitTotals {
  total_with_tax: number;
  total_net: number;
  products_with_tax: number;
  products_net: number;
  shipping_with_tax: number;
  shipping_net: number;
  order_count: number;
  return_count: number;
}

export interface CorrispettivoDaySummary {
  date: string;
  sales: CorrispettivoSplitTotals;
  returns: CorrispettivoSplitTotals;
  net: CorrispettivoSplitTotals;
}

export interface CorrispettivoListResponse {
  year: number;
  month: number;
  timezone: string;
  days: CorrispettivoDaySummary[];
  month_totals: CorrispettivoSplitTotals;
}

export interface CorrispettivoExportRequest {
  year: number;
  month: number;
  filters?: CorrispettivoFilters;
}
```

---

## 8. NgRx — struttura suggerita

```
src/app/features/corrispettivi/
├── models/corrispettivo.models.ts
├── services/corrispettivo-api.service.ts
├── store/
│   ├── corrispettivi.actions.ts
│   ├── corrispettivi.effects.ts
│   ├── corrispettivi.reducer.ts
│   ├── corrispettivi.selectors.ts
│   └── corrispettivi.state.ts
├── components/
│   ├── corrispettivi-filters/
│   ├── corrispettivi-riepilogo-table/
│   └── corrispettivi-summary/
└── pages/corrispettivi-page/
```

**State minimo:**
```typescript
interface CorrispettiviState {
  filters: CorrispettivoFilters;
  year: number;
  month: number;
  riepilogo: CorrispettivoRiepilogoResponse | null;
  summary: CorrispettivoListResponse | null;
  loading: boolean;
  exporting: boolean;
  error: string | null;
}
```

**Actions principali:**
- `loadRiepilogo` / `loadRiepilogoSuccess` / `loadRiepilogoFailure`
- `loadSummary` / … (opzionale)
- `exportRegistri` / `exportRegistriSuccess` / `exportRegistriFailure`
- `setFilters`, `setPeriod`

---

## 9. File sorgente backend

| File | Ruolo |
|---|---|
| `src/routers/corrispettivi.py` | Endpoint HTTP |
| `src/schemas/corrispettivo_schema.py` | Contratti Pydantic / OpenAPI |
| `src/services/routers/corrispettivo_service.py` | Orchestrazione |
| `src/repository/corrispettivo_repository.py` | Query SQL aggregate |
| `src/services/corrispettivi/aggregation.py` | Costruzione matrice |
| `src/services/export/corrispettivi_excel_service.py` | ZIP + Excel |

---

## 10. Test backend

```bash
pytest tests/unit/services/corrispettivi/test_corrispettivi_aggregation.py -v
```

---

## Changelog

| Data | Modifica |
|---|---|
| 2026-07-06 | Diagnostica 401 migliorata (`authorization_header_present` in log e body); alias `/riepilogo/` e `/summary` |
| 2026-07-06 | Rimosso `GET /aliquote` (ridondante: header aliquote in `/riepilogo` → `columns`) |
| 2026-07-06 | Fix SQLAlchemy `EXISTS` correlazione su filtro ordini non fatturati (500 su GET `/`) |
| 2026-07-06 | Prima release API corrispettivi (riepilogo, summary, export) |
