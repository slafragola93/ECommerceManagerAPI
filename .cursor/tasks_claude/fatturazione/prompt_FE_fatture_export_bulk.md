# Prompt FE — Export massivo lista fatture (Excel / XML)

Copia tutto il contenuto **sotto la riga `---`** e incollalo in una nuova chat Cursor sul **repository del gestionale Angular**.

Handoff BE: sezione *Export massivo lista fatture* in `README.md` e **matrice endpoint output** in [`docs/FATTURAPA.md`](../../../docs/FATTURAPA.md) §6 (repo **ECommerceManagerAPI**).  
Pattern export già implementato sul FE per le **Ricevute** → riusare stesso approccio (`responseType: 'blob'`, helper download, filtri lista).

**Obiettivo sessione:** collegare la **lista fatture** all'export bulk BE — **Excel e XML FatturaPA (ZIP)**.  
Il **PDF si scarica solo per singola fattura** (dettaglio/riga lista), **non** in bulk.

Il contenuto/colonne dei file export potrà essere rifinito in un secondo momento: priorità a **wire-up API, filtri, download e gestione errori**.

---

## Contesto

| Cosa | Stato BE | Stato FE atteso |
|------|----------|-----------------|
| Lista fatture paginata | ✅ `GET /api/v1/fiscal_documents/?document_type=invoice` | Probabilmente ✅ |
| **PDF singola fattura** | ✅ `GET /api/v1/fiscal_documents/{id}/pdf` | Verificare / mantenere |
| Export bulk Excel | ✅ `GET .../invoices/export?fmt=xlsx` | Da verificare / completare |
| Export bulk **XML** (ZIP) | ✅ `GET .../invoices/export?fmt=xml` | **Manca — implementare** |
| Export bulk PDF | ❌ **Non disponibile** | **Non implementare** |
| Filtro paese consegna | ✅ `delivery_country_iso` su export | **Manca — implementare** |

---

## Autenticazione e permessi

Base export bulk: `{API_BASE}/api/v1/fiscal_documents/invoices/export`  
PDF singola: `{API_BASE}/api/v1/fiscal_documents/{id}/pdf`  
Header: `Authorization: Bearer <JWT>`

| Azione | Permesso |
|--------|----------|
| Export massivo Excel/XML | `fiscal_documents:read` |
| Download PDF singola | `fiscal_documents:read` |

---

## API — export massivo (fonte di verità)

### Endpoint bulk

```http
GET /api/v1/fiscal_documents/invoices/export
```

### Query params

| Param | `xlsx` | `xml` | Note |
|-------|--------|-------|------|
| `fmt` | ✓ | ✓ | Default BE: `xlsx`. **`pdf` non è accettato.** |
| `delivery_country_iso` | ✓ | ✓ | ISO paese **consegna** (es. `IT`, `FR`, `DE`) |
| `date_add_from` | ✓ | ✓ | Data emissione da (`YYYY-MM-DD`, campo `date_add`) |
| `date_add_to` | ✓ | ✓ | Data emissione a |
| `is_electronic` | ✓ | **ignorato** | Solo Excel |
| `status` | ✓ | **ignorato** | Solo Excel — **nessun vincolo di stato per XML** |
| `id_order` | ✓ | **ignorato** | Solo Excel |
| `id_customer` | ✓ | **ignorato** | Solo Excel |

### Formati output bulk

| `fmt` | Content-Type | File scaricato | Max record |
|-------|--------------|----------------|------------|
| `xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | `fatture-export{suffix}.xlsx` | **5000** |
| `xml` | `application/zip` | `fatture-xml-export{suffix}.zip` | **5000** |

Ogni XML nello ZIP usa il nome SDI `[IdPaese][IdCodice]_[ProgressivoInvio].xml` (es. `IT08632861210_101164.xml`), ricavato dal contenuto FatturaPA — non dal nome file eventualmente salvato in DB con convenzioni legacy del portale.

**Suffisso filename** (BE): include `-{ISO}` se filtrato per paese + range date, es.  
`fatture-export-IT-2026-01-01-2026-01-31.xlsx`, `fatture-xml-export-FR.zip`.

### PDF — solo singola fattura

```http
GET /api/v1/fiscal_documents/{id_fiscal_document}/pdf
```

- `responseType: 'blob'`
- Content-Type: `application/pdf`
- Filename: `fattura-{numero}.pdf` o `nota-credito-{numero}.pdf`
- Azione UI: icona/bottone **Scarica PDF** su riga lista o pagina dettaglio — **non** nel menu export bulk.

---

## ⚠️ Regole business importanti

### 1. Paese = consegna (non fatturazione)

Il filtro `delivery_country_iso` usa l'indirizzo di **consegna** dell'ordine (`id_address_delivery`), **non** quello di fatturazione.

Motivo: l'aliquota IVA segue il paese di spedizione (stessa logica di corrispettivi e tax engine ordine).

**UI:** etichetta consigliata → *Paese consegna* / *Paese spedizione* — **non** «Paese fatturazione».

### 2. Export XML — nessun vincolo di stato

Per l'export XML **non** esistono condizioni su status, `is_electronic`, ordine o cliente.

**Filtri effettivi:** solo `delivery_country_iso`, `date_add_from`, `date_add_to`.

- Tutte le fatture nel range/paese vengono candidate.
- Se `xml_content` manca, il BE tenta la **generazione automatica** FatturaPA (come `POST /{id}/generate-xml`).
- Se **nessuna** fattura è esportabile (validazione fallita o set vuoto) → **400/404** con dettagli in `details.failed[]`.
- Se **alcune** falliscono ma altre ok → ZIP con le fatture riuscite (eventuale warning in risposta se previsto).

**UI export XML:** mostrare solo filtri **paese consegna** + **range date** — non passare `status` / `is_electronic` dalla lista.

### 3. Limiti e errori export bulk

| Caso | HTTP | Azione FE |
|------|------|-----------|
| Nessuna fattura con i filtri | 404 | Toast «Nessuna fattura trovata» |
| Troppi record (> 5000) | 400 | Toast con invito a restringere filtri |
| `fmt=pdf` o formato invalido | 400 | Non offrire PDF nel menu bulk |
| XML: tutte le fatture del set falliscono generazione | 400 | Mostrare `details.failed[]` |

### 4. Filtri export ≠ filtri lista (per ora)

La lista paginata `GET /api/v1/fiscal_documents/` **non** espone ancora `delivery_country_iso` né range date.

L'export ha filtri **più ricchi**: passare alla chiamata export i filtri attivi nella UI lista **più** eventuali filtri export-only (paese, date).

---

## TypeScript — modelli

File suggerito: `src/app/core/models/invoice-export.model.ts`

```typescript
/** Solo formati bulk — il PDF non è incluso */
export type InvoiceBulkExportFormat = 'xlsx' | 'xml';

export type FiscalDocumentStatus =
  | 'pending'
  | 'generated'
  | 'uploaded'
  | 'sent'
  | 'error'
  | 'issued';

export interface InvoiceExportFilters {
  is_electronic?: boolean;
  status?: FiscalDocumentStatus;
  id_order?: number;
  id_customer?: number;
  /** ISO paese CONSEGNA — determina IVA */
  delivery_country_iso?: string;
  date_add_from?: string; // YYYY-MM-DD
  date_add_to?: string;
}

export interface InvoiceBulkExportOptions extends InvoiceExportFilters {
  fmt: InvoiceBulkExportFormat;
}
```

---

## Service Angular — implementazione

File suggerito: `src/app/core/services/fiscal-documents.service.ts`

### Export bulk (Excel / XML)

```typescript
exportInvoicesBulk(options: InvoiceBulkExportOptions): Observable<Blob> {
  let params = new HttpParams().set('fmt', options.fmt);
  // ... stessi query param di InvoiceExportFilters (vedi prompt precedente)
  return this.http.get(
    `${this.apiBase}/api/v1/fiscal_documents/invoices/export`,
    { params, responseType: 'blob', observe: 'response' }
  );
}
```

### PDF singola (dettaglio / riga lista)

```typescript
downloadInvoicePdf(idFiscalDocument: number): Observable<Blob> {
  return this.http.get(
    `${this.apiBase}/api/v1/fiscal_documents/${idFiscalDocument}/pdf`,
    { responseType: 'blob' }
  );
}
```

---

## UI — schermata lista fatture

### Menu Export bulk (solo 2 voci)

| Voce | `fmt` | Note |
|------|-------|------|
| Excel | `xlsx` | Export riepilogo lista |
| **XML FatturaPA (ZIP)** | `xml` | **Nuovo** — solo fatture elettroniche con XML |

**Non** includere «Export PDF» o «PDF (ZIP)» nel menu bulk.

### Azione PDF per singola fattura

- Icona **PDF** sulla riga tabella e/o bottone in dettaglio fattura.
- Chiama `GET /{id}/pdf` — stesso pattern già usato per ricevute/DDT.

### Filtri UI (barra lista)

| Filtro | Binding | Note |
|--------|---------|------|
| Stato | `status` | select |
| Elettronica | `is_electronic` | tri-state |
| Paese consegna | `delivery_country_iso` | select ISO — **nuovo** |
| Data da / a | `date_add_from`, `date_add_to` | date picker |

I filtri attivi vanno passati **identici** alla chiamata export bulk.

### Loading / feedback

- Disabilitare export bulk durante download.
- Toast successo con nome file.
- Gestire errori 400/404.

---

## Scenari di test manuali

| # | Scenario | Atteso |
|---|----------|--------|
| 1 | Export Excel senza filtri | Download `.xlsx` |
| 2 | Export XML con `status=generated` | Download `.zip` con `.xml` FatturaPA |
| 3 | Export XML con fattura `pending` (no XML) | 400 |
| 4 | Filtro `delivery_country_iso=IT` | Filename con `-IT`; solo consegne IT |
| 5 | PDF da riga/dettaglio singola fattura | Download `.pdf` (non ZIP) |
| 6 | `fmt=pdf` su export bulk (se provato) | 400 — non esporre in UI |
| 7 | Range date invalido | Validazione FE |
| 8 | Utente senza permesso read | Export nascosto |

---

## Checklist implementazione FE

- [ ] Tipi `InvoiceBulkExportFormat` = `'xlsx' | 'xml'` (no `pdf`)
- [ ] `exportInvoicesBulk()` — solo xlsx/xml
- [ ] Menu bulk: **Excel** + **XML FatturaPA (ZIP)**
- [ ] **Nessuna** voce export PDF bulk
- [ ] PDF singola: bottone riga/dettaglio → `GET /{id}/pdf`
- [ ] Filtro **Paese consegna** collegato all'export
- [ ] Filtri date collegati all'export
- [ ] Helper download blob
- [ ] Gestione errori 400/404
- [ ] Tooltip export XML: «Richiede XML già generato»

---

## Non in scope

- Export bulk PDF (rimosso lato BE).
- Export singola fattura Excel/XML (solo bulk lista).
- Export note di credito.
- Generazione XML massiva dal FE.

---

## Riferimenti BE

| Risorsa | Path repo API |
|---------|---------------|
| README export | `README.md` → *Export massivo lista fatture* |
| Router bulk | `src/routers/fiscal_documents.py` → `GET /invoices/export` |
| Router PDF singola | `GET /{id_fiscal_document}/pdf` |
| Prompt fattura v3 | `.cursor/tasks_claude/fatturazione/prompt_FE_fatture_V3_ALIGN.md` |

---

## Definition of done

1. Export bulk: **Excel** e **XML (ZIP)** con filtri attivi.
2. **PDF solo singola** fattura (riga/dettaglio), non nel menu bulk.
3. Filtro **paese consegna** in UI export.
4. Export XML con gestione errori se manca XML generato.
