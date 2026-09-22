# Prompt FE — Genera fatture in blocco dalla lista ordini

Copia tutto il contenuto **sotto la riga `---`** e incollalo in una nuova chat Cursor sul **repository del gestionale Angular**.

Handoff BE: sezione *Bulk create fatture* in `README.mdc` e [`docs/FATTURAPA.md`](../../../docs/FATTURAPA.md) §4 (repo **ECommerceManagerAPI**).  
Pattern UI già presente per **bulk LDV** (`POST /shipments/bulk-create`) e **bulk-status** ordini → riusare toast/modale con `successful` / `failed` / `summary`.

**Obiettivo sessione:** dalla **lista ordini**, con selezione multipla, azione **“Genera fatture”** che chiama il nuovo endpoint BE e mostra l’esito per-ordine.

---

## Contesto

| Cosa | Stato BE | Stato FE atteso |
|------|----------|-----------------|
| Crea fattura singola | ✅ `POST /api/v1/fiscal_documents/invoices` | Probabilmente ✅ (dettaglio ordine) |
| **Bulk create da lista ordini** | ✅ `POST .../invoices/bulk-create` | **Manca — implementare** |
| Generate-xml / send-to-sdi | ✅ endpoint singoli | **Non chiamare** dal bulk |
| Flag `has_invoice` in lista | ✅ su GET ordini | Usare per disabilitare / feedback |
| Re-emissione | ✅ solo `POST /invoices` singolo | **Non** nel bulk |

---

## Autenticazione e permessi

```http
POST /api/v1/fiscal_documents/invoices/bulk-create
Authorization: Bearer <JWT>
Content-Type: application/json
```

| Azione | Permesso |
|--------|----------|
| Bulk create fatture | `fiscal_documents:create` |

---

## API — contratto

### Request

```json
{ "order_ids": [101, 102, 103] }
```

| Campo | Validazione |
|-------|-------------|
| `order_ids` | obbligatorio, `min 1`, `max 100`, ogni id `> 0` |
| duplicati | il BE li deduplica; meglio deduplicare anche lato FE |

### Response 200 (sempre se body valido)

```json
{
  "successful": [
    {
      "order_id": 101,
      "id_fiscal_document": 8801,
      "document_number": "000123",
      "status": "pending"
    }
  ],
  "failed": [
    {
      "order_id": 102,
      "error_type": "ALREADY_INVOICED",
      "error_message": "Ordine già fatturato: usare la re-emissione sul singolo ordine"
    }
  ],
  "summary": {
    "total": 2,
    "successful_count": 1,
    "failed_count": 1
  }
}
```

HTTP 200 anche se **tutti** falliscono. Errori HTTP del request: 401/403, 422 (body vuoto / >100 id / id non validi).

### `error_type` possibili

| `error_type` | UI suggerita |
|---|---|
| `ALREADY_INVOICED` | “Già fatturato” — link/azione re-emissione solo da dettaglio |
| `NOT_FOUND` | “Ordine non trovato” |
| `BUSINESS_RULE_ERROR` | messaggio BE (ricevuta/reso) |
| `VALIDATION_ERROR` | messaggio BE (es. indirizzo fatturazione mancante) |
| `UNKNOWN_ERROR` | errore generico + messaggio |

---

## Implementazione FE consigliata

### 1. Lista ordini — azione bulk

- Checkbox selezione (già presente per LDV / cambio stato).
- Voce menu / bottone: **“Genera fatture”**.
- Se **tutti** i selezionati hanno `has_invoice === true` → disabilitare l’azione (il BE rifiuterebbe comunque con `ALREADY_INVOICED`).
- Opzionale: filtrare i selezionati e inviare solo quelli con `has_invoice === false`, oppure inviare tutti e mostrare i failed.

### 2. Service Angular

```typescript
export interface BulkInvoiceCreateRequest {
  order_ids: number[];
}

export interface BulkInvoiceCreateSuccess {
  order_id: number;
  id_fiscal_document: number;
  document_number?: string | null;
  status?: string | null;
}

export interface BulkInvoiceCreateError {
  order_id: number;
  error_type: string;
  error_message: string;
}

export interface BulkInvoiceCreateResponse {
  successful: BulkInvoiceCreateSuccess[];
  failed: BulkInvoiceCreateError[];
  summary: {
    total: number;
    successful_count: number;
    failed_count: number;
  };
}

bulkCreateInvoices(orderIds: number[]): Observable<BulkInvoiceCreateResponse> {
  return this.http.post<BulkInvoiceCreateResponse>(
    `${API_BASE}/api/v1/fiscal_documents/invoices/bulk-create`,
    { order_ids: orderIds }
  );
}
```

### 3. UX post-chiamata

1. Conferma (modale): “Generare N fatture per gli ordini selezionati?”
2. Loading finché risponde il BE.
3. Toast / dialog:
   - `summary.successful_count` create
   - elenco `failed` (order_id + messaggio)
4. **Refresh lista ordini** → `has_invoice` true sui successi.
5. **Non** chiamare `generate-xml` né `send-to-sdi` in automatico.

### 4. Fuori scope

- Re-emissione / seconda fattura → resta sul **dettaglio** via `POST /invoices` singolo.
- Export Excel/XML fatture → già altro flusso (`GET /invoices/export`).
- PDF → solo singolo `GET /{id}/pdf`.

---

## Checklist

- [ ] Tipi `BulkInvoiceCreate*` nel service fiscal/documents o orders
- [ ] Azione “Genera fatture” su selezione lista ordini
- [ ] Disabilitazione se tutti `has_invoice`
- [ ] Gestione 422 (max 100) e 403
- [ ] Modale/toast con `summary` + `failed`
- [ ] Refresh lista dopo successo
- [ ] Nessuna chiamata generate-xml / send-to-sdi dal bulk
- [ ] “Riemetti fattura” non nel menu bulk

---

## File BE di riferimento

| Cosa | Path |
|------|------|
| Router | `src/routers/fiscal_documents.py` → `POST /invoices/bulk-create` |
| Service | `src/services/routers/fiscal_document_service.py` → `bulk_create_invoices` |
| Schema | `src/schemas/fiscal_document_schema.py` → `BulkInvoiceCreate*` |
| Docs | `docs/FATTURAPA.md` §4 bulk-create |
| Test | `tests/unit/services/test_bulk_create_invoices.py` |
