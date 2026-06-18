# Prompt sessione FE — Stampa PDF DDT

Copia tutto il contenuto sotto la riga `---` e incollalo in una nuova chat Cursor/Claude sul **repository del gestionale Angular** (creative_light3 o equivalente).

**Prerequisito:** BE **ECommerceManagerAPI** deployato con fix PDF DDT (Fase 1–2, 2026-06-16). Handoff completo: `docs/FE_HANDOFF_DDT_PRINT_PDF.md` nel repo BE.

---

## Contesto

Il backend genera il PDF del Documento di Trasporto (mittente, destinatario, articoli, IVA, spedizione, colli, firme).  
Il FE **non** compone HTML di stampa: scarica il blob PDF e lo apre in nuova tab.

### Obiettivo

Integrare il bottone **«Stampa DDT»** nel dettaglio DDT (modale o pagina) e opzionalmente nel menu riga lista, riusando lo stesso pattern già usato per:

- PDF preventivo → `quotes.service.ts` / `downloadPdf(id): Observable<Blob>`
- PDF ordine → `orders.service.ts` / `downloadOrderPdf(id): Observable<Blob>`
- Borderò → `generateBordero(...)` + `window.open`

---

## API Backend (contratto v1)

```http
GET {API_BASE}/api/v1/ddt/pdf/{id_order_document}
Authorization: Bearer <JWT>
```

| Response | Dettaglio |
|----------|-----------|
| **200** | `application/pdf`, `Content-Disposition: attachment; filename="DDT-{document_number}.pdf"` |
| **404** | `{ "detail": "DDT non trovato" }` |
| **403** | permesso mancante (`ddt.read`) |
| **500** | errore generazione PDF |

- Usare sempre **`id_order_document`** (PK del documento DDT), **non** `id_order` né `document_number` nel path.
- Nessun body request.

---

## Task FE (checklist)

### 1) Service HTTP

Aggiungere in `ddt.service.ts` (o service API documenti):

```typescript
downloadDdtPdf(idOrderDocument: number): Observable<Blob> {
  return this.http.get(
    `${this.apiBase}/api/v1/ddt/pdf/${idOrderDocument}`,
    { responseType: 'blob' }
  );
}
```

### 2) Handler UI (dettaglio DDT)

- Bottone toolbar **«Stampa DDT»** (icona `print`)
- Visibile se utente ha accesso modulo DDT (opzionale check RBAC `ddt.read`)
- On click:
  1. `loading = true`
  2. `downloadDdtPdf(selectedDdt.id_order_document)`
  3. On success: `URL.createObjectURL(blob)` → `window.open(url, '_blank')`
  4. Fallback se popup bloccato: `<a download="DDT-{document_number}.pdf">`
  5. On error: parse blob JSON se 404/500, toast/Swal
  6. `loading = false` in `finalize`

**(Opzionale)** Auto-stampa: `win?.addEventListener('load', () => win.print())`

### 3) Error handling blob

Su `HttpErrorResponse` con `err.error instanceof Blob`, fare `await err.error.text()` + `JSON.parse` per leggere `detail`.

### 4) (Opzionale) Lista DDT

Voce menu contestuale «Stampa DDT» che riusa lo stesso handler passando `ddt.id_order_document`.

---

## Vincoli / non fare

- ❌ Non costruire template HTML stampa DDT lato FE
- ❌ Non usare `id_order` o `document_number` nel path PDF (solo `id_order_document`)
- ❌ Non fare GET DDT completo solo per stampare (il BE carica tutto)
- ❌ Non cambiare contratto API (layout PDF è server-side)

---

## File FE probabili da toccare

(adattare ai path reali del repo Angular)

| File | Modifica |
|------|----------|
| `src/app/core/services/ddt.service.ts` | `downloadDdtPdf()` |
| Componente dettaglio DDT (modale o pagina) `.ts` | handler + loading |
| Componente dettaglio DDT `.html` | bottone toolbar |
| Lista DDT `.ts` | (opz.) menu riga |

---

## Test manuali

1. Apri dettaglio DDT con righe + spedizione → Stampa → PDF in nuova tab.
2. Verifica colonna IVA (es. 22%, non valori tipo 3 = id tax).
3. DDT con 2+ pacchi → colli corretti nel PDF.
4. DDT inesistente (id fake) → messaggio errore.
5. Popup blocker attivo → download file funziona.

---

## Definition of done

- [ ] `downloadDdtPdf` nel service
- [ ] Bottone dettaglio DDT funzionante
- [ ] Blob + nuova tab (o download fallback)
- [ ] Errori 404/500 gestiti
- [ ] Path usa `id_order_document`
- [ ] Nessuna regressione su stampa preventivo / ordine / borderò

---

## Riferimento BE (solo lettura)

Repo: **ECommerceManagerAPI**  
Endpoint: `src/routers/ddt.py` → `generate_ddt_pdf`  
PDF: `src/services/pdf/ddt_pdf_service.py`  
Handoff: `docs/FE_HANDOFF_DDT_PRINT_PDF.md`
