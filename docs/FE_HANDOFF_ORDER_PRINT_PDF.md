# FE — Stampa PDF singolo ordine

Guida per il gestionale Angular (repo FE separato). Il backend **ECommerceManagerAPI** espone l’endpoint; il layout PDF è interamente lato server (stile documento ordine elettronew).

**Prompt da incollare in chat FE (Cursor/Claude):** [.cursor/tasks_claude/prompt_FE_order_print_pdf.md](../.cursor/tasks_claude/prompt_FE_order_print_pdf.md)

---

## Contesto

In passato la stampa ordine poteva essere HTML client-side o su Smarty. Ora il BE genera un PDF coerente con il documento cartaceo elettronew:

- Logo + anagrafica società (`company_info`)
- Barcode Code39 + titolo `ORDINE - {codice}`
- Blocchi **Intestazione** / **Indirizzo di consegna**
- Tabella righe: Codice, Descrizione, Impon., IVA, Sconto, Quant., Totale
- Riepilogo totali a destra (merce, spedizione, spese incasso, IVA, totale)
- Note ordine + paginazione

Il FE deve solo **scaricare il blob** e aprirlo in nuova tab (eventualmente `window.print()`).

---

## API

```http
GET /api/v1/orders/{id_order}/pdf
Authorization: Bearer <JWT>
```

| Aspetto | Valore |
|---------|--------|
| **Permesso RBAC** | `orders` + azione `read` |
| **Body** | nessuno |
| **Response 200** | `Content-Type: application/pdf` |
| **Content-Disposition** | `inline; filename="Ordine-{id_order}.pdf"` |
| **404** | `{ "detail": "Ordine non trovato" }` |
| **401/403** | auth / permessi (interceptor esistente) |
| **500** | errore generazione PDF (`detail` testuale) |

**Identificatore:** usare sempre la **PK gestionale** `id_order` (non `id_origin` PrestaShop).

### Barcode e titolo ordine (generati lato BE)

| Elemento | Regola |
|----------|--------|
| **Barcode Code39** | Valore numerico: `id_origin` se ordine PS (`> 0`), altrimenti `id_order`. Render con `fpdf2` `code39("*{valore}*")` (asterischi start/stop Code39). |
| **Titolo `ORDINE - …`** | `internal_reference` se presente; altrimenti `SM{id_origin}` (legacy PS); altrimenti `id_order`. |
| **Riga `n° … del …`** | `orders.reference` + `orders.date_add` |

Il barcode e l’etichetta possono differire (es. barcode `805260`, titolo `ORDINE - SM805260` se `internal_reference=SM805260`).

---

## Pattern FE consigliato (allineato a preventivi / borderò)

Riferimenti nel gestionale Angular (nomi indicativi):

| Feature esistente | Pattern da riusare |
|-------------------|-------------------|
| PDF preventivo | `quotes.service.ts` → `downloadPdf(id): Observable<Blob>` |
| Borderò spedizioni | `orders.service.ts` → `generateBordero(...): Observable<Blob>` + `window.open` |

### Service HTTP

```typescript
downloadOrderPdf(orderId: number): Observable<Blob> {
  return this.http.get(
    `${this.apiBase}/api/v1/orders/${orderId}/pdf`,
    { responseType: 'blob' }
  );
}
```

### Apertura + stampa

```typescript
downloadOrderPdf(orderId: number): void {
  this.loading = true;
  this.ordersApi.downloadOrderPdf(orderId).pipe(
    finalize(() => (this.loading = false))
  ).subscribe({
    next: (blob) => {
      const url = URL.createObjectURL(blob);
      const win = window.open(url, '_blank');
      if (!win) {
        // fallback download diretto
        const a = document.createElement('a');
        a.href = url;
        a.download = `Ordine-${orderId}.pdf`;
        a.click();
      }
      // opzionale: auto-print quando la tab è pronta (come borderò)
      // win?.addEventListener('load', () => win.print());
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
      return json.detail ?? 'Errore generazione PDF';
    } catch {
      return 'Errore generazione PDF';
    }
  }
  return err.message ?? 'Errore generazione PDF';
}
```

---

## Dove mettere il pulsante

| Posizione | Priorità | Note |
|-----------|----------|------|
| Modale dettaglio ordine (`OrderDetailsModalComponent`) | **Alta** | Toolbar azioni documenti / stampa |
| Lista ordini (riga o menu contestuale) | Media | Opzionale, stesso handler |

**Etichetta suggerita:** «Stampa ordine» (icona `print` Material).

**Visibilità:** solo se l’utente ha permesso `orders.read` (di solito già vero sulla route ordini).

**Stati UX:**

- `loading` sul bottone durante la richiesta
- Disabilitare doppio click
- Toast/alert su 404 o 500

Non serve payload ordine lato FE: il BE legge ordine, righe, indirizzi, pagamento e spedizione dal DB.

---

## Checklist implementazione FE

- [ ] Metodo `downloadOrderPdf(id_order)` in `orders.service.ts` (o service API dedicato)
- [ ] Bottone in modale dettaglio ordine
- [ ] `responseType: 'blob'` + apertura nuova tab
- [ ] Gestione errori 404/500 su risposta blob
- [ ] (Opzionale) `window.print()` automatico dopo load tab
- [ ] (Opzionale) voce menu contestuale in lista ordini
- [ ] Test manuale su ordine reale con righe, sconto, spedizione, note

---

## QA congiunto BE ↔ FE

| # | Scenario | Esito atteso |
|---|----------|--------------|
| 1 | Click «Stampa ordine» su ordine valido | Nuova tab con PDF leggibile |
| 2 | Layout PDF | Logo, barcode, intestazione/consegna, tabella, totali coerenti |
| 3 | Ordine con sconto riga | Colonna Sconto % valorizzata |
| 4 | Ordine con note (`general_note`) | Sezione NOTE popolata |
| 5 | `id_order` inesistente | 404 + messaggio utente |
| 6 | Utente senza `orders.read` | 403 |
| 7 | Popup blocker | Fallback download file `Ordine-{id}.pdf` |

---

## Riferimenti BE

| File | Ruolo |
|------|--------|
| `src/routers/order.py` | Endpoint `GET /{order_id}/pdf` |
| `src/services/routers/order_service.py` | `generate_order_pdf` |
| `src/services/pdf/order_pdf_service.py` | Layout PDF |

Deploy BE richiesto prima del test FE in ambiente condiviso.
