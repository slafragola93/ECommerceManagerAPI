# Prompt FE — Invio SDI in blocco (lista fatture)

Copia tutto il contenuto **sotto la riga `---`** e incollalo in una nuova chat Cursor sul **repository del gestionale Angular**.

Handoff BE: sezione *Bulk invio SDI* in `README.mdc` e [`docs/FATTURAPA.md`](../../../docs/FATTURAPA.md) §6 (repo **ECommerceManagerAPI**).  
Pattern UI già presente per **bulk-create fatture** e **bulk LDV** → riusare toast/modale con `successful` / `failed` / `summary`.

**Obiettivo sessione:** dalla **lista fatture**, con selezione multipla, azione **“Invia a SDI”** che chiama il nuovo endpoint BE facade.

---

## Contesto importante

FatturaPA.com **non** accetta un array di file in una sola call API. Il BE fa **N cicli** `UploadStart1 → blob → UploadStop` dietro un’unica HTTP dal FE.

| Cosa | Stato BE | Stato FE atteso |
|------|----------|-----------------|
| Send-to-sdi singolo | ✅ `POST .../{id}/send-to-sdi` | Probabilmente ✅ |
| **Bulk send-to-sdi** | ✅ `POST .../send-to-sdi/bulk` | **Manca — implementare** |
| Retry dopo NS | ✅ `POST .../{id}/retry-send` | **Non** nel bulk |
| Auto generate-xml nel bulk | ❌ | Non chiamare generate-xml dal bulk |
| Export ZIP XML | ✅ `GET .../invoices/export?fmt=xml` | Solo download — **non** è invio SDI |

---

## Autenticazione e permessi

```http
POST /api/v1/fiscal_documents/send-to-sdi/bulk
Authorization: Bearer <JWT>
Content-Type: application/json
```

| Azione | Permesso |
|--------|----------|
| Bulk send-to-sdi | `fiscal_documents:update` |

---

## API — contratto

### Request

```json
{ "ids": [8801, 8802, 8803], "send_to_sdi": true }
```

| Campo | Validazione |
|-------|-------------|
| `ids` | obbligatorio, min 1, max **25**, ogni id `> 0` |
| `send_to_sdi` | default `true` — lasciare `true` dall’azione “Invia a SDI” |
| duplicati | il BE li deduplica |

### Response 200 (sempre se body valido)

```json
{
  "successful": [
    { "id_fiscal_document": 8801, "status": "sent", "sdi_status": null }
  ],
  "failed": [
    {
      "id_fiscal_document": 8802,
      "error_type": "XML_MISSING",
      "error_message": "XML non ancora generato. Chiamare prima /generate-xml"
    }
  ],
  "summary": {
    "total": 2,
    "successful_count": 1,
    "failed_count": 1
  }
}
```

Errori HTTP del request: 401/403, **400** se API SDI disabilitata, **422** (body vuoto / >25 id / id non validi).

### `error_type` possibili

| `error_type` | UI suggerita |
|---|---|
| `XML_MISSING` | “XML mancante — genera XML prima” |
| `BLOCKED` | messaggio BE (già inviata / usa Reinvia se scartata) |
| `PEC_GATE` | “PEC obbligatoria per destinatario estero” |
| `NOT_ELECTRONIC` | non inviabile |
| `NOT_FOUND` | documento non trovato |
| `UPLOAD_ERROR` | errore intermediario |
| `UNKNOWN_ERROR` | errore generico |

---

## Implementazione FE consigliata

### 1. Lista fatture — azione bulk

- Checkbox selezione.
- Voce: **“Invia a SDI”**.
- Abilitare solo se almeno un selezionato ha XML / stato idoneo (`generated` / `uploaded` / `error`, non `pending`, non già `sent` in attesa, non `scartata`).
- Documenti `scartata` (NS): escluderli e suggerire **Reinvia** sul singolo (`retry-send`).

### 2. Service Angular

```typescript
export interface BulkSendToSdiRequest {
  ids: number[];
  send_to_sdi?: boolean; // default true
}

export interface BulkSendToSdiSuccess {
  id_fiscal_document: number;
  status?: string | null;
  sdi_status?: string | null;
}

export interface BulkSendToSdiError {
  id_fiscal_document: number;
  error_type: string;
  error_message: string;
}

export interface BulkSendToSdiResponse {
  successful: BulkSendToSdiSuccess[];
  failed: BulkSendToSdiError[];
  summary: {
    total: number;
    successful_count: number;
    failed_count: number;
  };
}

bulkSendToSdi(ids: number[]): Observable<BulkSendToSdiResponse> {
  return this.http.post<BulkSendToSdiResponse>(
    `${API_BASE}/api/v1/fiscal_documents/send-to-sdi/bulk`,
    { ids, send_to_sdi: true }
  );
}
```

### 3. UX

1. Conferma: “Inviare N documenti a SDI?”
2. Loading (può richiedere diversi secondi: N × upload esterni; max 25).
3. Toast/dialog con `summary` + elenco `failed`.
4. Refresh lista (`status` / `sdi_status`).
5. **Non** confondere con export ZIP XML (solo download contabile).

### 4. Fuori scope

- `retry-send` dopo NS → solo dettaglio singolo
- Auto `generate-xml` in batch → non implementare
- Job async / progress bar server-side → non richiesto in questa sessione

---

## Checklist

- [ ] Tipi `BulkSendToSdi*`
- [ ] Azione “Invia a SDI” su selezione lista fatture
- [ ] Filtro / disable se nessuno idoneo; escludere NS
- [ ] Gestione 400 (API off), 422 (max 25)
- [ ] Modale/toast con `summary` + `failed`
- [ ] Refresh lista dopo risposta
- [ ] Nessuna confusione con export `fmt=xml`

---

## File BE di riferimento

| Cosa | Path |
|------|------|
| Router | `src/routers/fiscal_documents.py` → `POST /send-to-sdi/bulk` |
| Service | `src/services/routers/fiscal_document_service.py` → `bulk_send_to_sdi` |
| Schema | `src/schemas/fiscal_document_schema.py` → `BulkSendToSdi*` |
| Finalize | `src/services/external/fatturapa_upload_finalize.py` |
| Docs | `docs/FATTURAPA.md` §6 |
| Test | `tests/unit/services/test_bulk_send_to_sdi.py` |
