# FE — Stampa PDF DDT

Guida per il gestionale Angular (repo FE separato). Il backend **ECommerceManagerAPI** espone l’endpoint; il layout PDF è interamente lato server (`DDTPDFService`).

**Prompt da incollare in chat FE (Cursor/Claude):** [.cursor/tasks_claude/prompt_FE_ddt_print_pdf.md](../.cursor/tasks_claude/prompt_FE_ddt_print_pdf.md)

---

## Contesto

Il modulo DDT espone già CRUD e dettaglio documento. La stampa PDF era implementata lato BE ma restituiva **500** (fix Fase 1–2 completata il 2026-06-16).

Il FE deve solo **scaricare il blob** e aprirlo in nuova tab (eventualmente `window.print()`).

Contenuto PDF (server-side):

- Logo mittente + anagrafica (`ddt_sender_*` / logo store)
- Titolo `DOCUMENTO DI TRASPORTO n. {document_number}`
- Box **Mittente** / **Destinatario**
- Riferimento ordine collegato (se presente)
- Tabella articoli: Codice, Descrizione, Qta, Prezzo, IVA %, Totale
- Info spedizione: quantità, peso, **colli** (da `packages`)
- Riepilogo IVA e totali
- Sezione firme trasporto + note

---

## API

```http
GET /api/v1/ddt/pdf/{id_order_document}
Authorization: Bearer <JWT>
```

| Aspetto | Valore |
|---------|--------|
| **Permesso RBAC** | `ddt` + azione `read` |
| **Body** | nessuno |
| **Response 200** | `Content-Type: application/pdf` |
| **Content-Disposition** | `attachment; filename="DDT-{document_number}.pdf"` |
| **404** | `{ "detail": "DDT non trovato" }` |
| **401/403** | auth / permessi (interceptor esistente) |
| **500** | errore generazione PDF (`detail` testuale) |

**Identificatore:** usare sempre la **PK gestionale** `id_order_document` (non `id_order`, non `document_number`).

| Campo UI tipico | Usare nel path PDF? |
|-----------------|---------------------|
| `id_order_document` | ✅ Sì |
| `document_number` | ❌ No (solo per filename in download fallback) |
| `id_order` | ❌ No |

---

## Pattern FE consigliato (allineato a ordini / preventivi)

| Feature esistente | Pattern da riusare |
|-------------------|-------------------|
| PDF preventivo | `quotes.service.ts` → `downloadPdf(id): Observable<Blob>` |
| PDF ordine | `orders.service.ts` → `downloadOrderPdf(id): Observable<Blob>` |
| Borderò spedizioni | `orders.service.ts` → `generateBordero(...)` + `window.open` |

### Service HTTP

```typescript
downloadDdtPdf(idOrderDocument: number): Observable<Blob> {
  return this.http.get(
    `${this.apiBase}/api/v1/ddt/pdf/${idOrderDocument}`,
    { responseType: 'blob' }
  );
}
```

> Adattare il path del service al repo (`ddt.service.ts` o service API documenti).

### Apertura + stampa

```typescript
downloadDdtPdf(idOrderDocument: number, documentNumber?: number): void {
  this.loading = true;
  this.ddtApi.downloadDdtPdf(idOrderDocument).pipe(
    finalize(() => (this.loading = false))
  ).subscribe({
    next: (blob) => {
      const url = URL.createObjectURL(blob);
      const win = window.open(url, '_blank');
      if (!win) {
        const a = document.createElement('a');
        a.href = url;
        a.download = `DDT-${documentNumber ?? idOrderDocument}.pdf`;
        a.click();
      }
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    },
    error: (err) => this.handlePdfError(err),
  });
}
```

### Gestione errori blob

Se l’interceptor non parsea JSON su `responseType: 'blob'`, in caso di 404/500 il body può essere un blob JSON:

```typescript
async function blobErrorMessage(err: HttpErrorResponse): Promise<string> {
  if (err.error instanceof Blob) {
    try {
      const text = await err.error.text();
      const json = JSON.parse(text);
      return json.detail ?? 'Errore generazione PDF DDT';
    } catch {
      return 'Errore generazione PDF DDT';
    }
  }
  return err.message ?? 'Errore generazione PDF DDT';
}
```

---

## Dove mettere il pulsante

| Posizione | Priorità | Note |
|-----------|----------|------|
| Modale / pagina dettaglio DDT | **Alta** | Toolbar azioni documenti / stampa |
| Lista DDT (riga o menu contestuale) | Media | Opzionale, stesso handler |

**Etichetta suggerita:** «Stampa DDT» (icona `print` Material).

**Visibilità:** solo se l’utente ha permesso `ddt.read` (di solito già vero sulla route DDT).

**Stati UX:**

- `loading` sul bottone durante la richiesta
- Disabilitare doppio click
- Toast/alert su 404 o 500

Non serve payload DDT lato FE: il BE legge documento, righe, indirizzi, spedizione e pacchi dal DB.

---

## Checklist implementazione FE

- [ ] Metodo `downloadDdtPdf(id_order_document)` in `ddt.service.ts` (o service API dedicato)
- [ ] Bottone in dettaglio DDT
- [ ] `responseType: 'blob'` + apertura nuova tab
- [ ] Gestione errori 404/500 su risposta blob
- [ ] Passare `id_order_document` dal modello DDT selezionato (non `id_order`)
- [ ] (Opzionale) `window.print()` automatico dopo load tab
- [ ] (Opzionale) voce menu contestuale in lista DDT
- [ ] Test manuale su DDT reale con righe, spedizione, più pacchi

---

## QA congiunto BE ↔ FE

| # | Scenario | Esito atteso |
|---|----------|--------------|
| 1 | Click «Stampa DDT» su DDT valido | Nuova tab con PDF leggibile |
| 2 | Layout PDF | Mittente/destinatario, tabella articoli, IVA % corretta (es. 22%, non id tax) |
| 3 | DDT con più pacchi | Colli = numero pacchi |
| 4 | DDT con note | Sezione NOTE popolata |
| 5 | `id_order_document` inesistente | 404 + messaggio utente |
| 6 | Utente senza `ddt.read` | 403 |
| 7 | Popup blocker | Fallback download `DDT-{document_number}.pdf` |

---

## Riferimenti BE

| File | Ruolo |
|------|--------|
| `src/routers/ddt.py` | Endpoint `GET /pdf/{id_order_document}` |
| `src/services/routers/ddt_service.py` | `generate_ddt_pdf`, `get_ddt_complete` |
| `src/services/pdf/ddt_pdf_service.py` | Layout PDF |
| `tests/unit/services/pdf/test_ddt_pdf_service.py` | Test regressione |

Deploy BE con fix Fase 1–2 richiesto prima del test FE in ambiente condiviso.
