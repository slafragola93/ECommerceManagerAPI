# Prompt sessione FE — Stampa PDF singolo ordine

Copia tutto il contenuto sotto la riga `---` e incollalo in una nuova chat Cursor/Claude sul **repository del gestionale Angular** (creative_light3 o equivalente).

**Prerequisito:** BE **ECommerceManagerAPI** deployato con `GET /api/v1/orders/{id}/pdf` testato. Handoff completo: `docs/FE_HANDOFF_ORDER_PRINT_PDF.md` nel repo BE.

---

## Contesto

Il backend genera il PDF di stampa ordine (layout elettronew legacy: logo, barcode, intestazione/consegna, tabella righe, totali).  
Il FE **non** deve più comporre HTML di stampa lato client: scarica il blob PDF e lo apre in nuova tab.

### Obiettivo

Integrare il bottone **«Stampa ordine»** nel modale dettaglio ordine (e opzionalmente nel menu riga lista), riusando lo stesso pattern già usato per:

- PDF preventivo → `quotes.service.ts` / `downloadPdf(id): Observable<Blob>`
- Borderò → `orders.service.ts` / `generateBordero(...): Observable<Blob>` + `window.open`

---

## API Backend (contratto v1)

```http
GET {API_BASE}/api/v1/orders/{id_order}/pdf
Authorization: Bearer <JWT>
```

| Response | Dettaglio |
|----------|-----------|
| **200** | `application/pdf`, `Content-Disposition: inline; filename="Ordine-{id_order}.pdf"` |
| **404** | `{ "detail": "Ordine non trovato" }` |
| **403** | permesso mancante (`orders.read`) |
| **500** | errore generazione PDF |

- Usare sempre **`id_order`** (PK gestionale), non `id_origin`.
- Nessun body request.

---

## Task FE (checklist)

### 1) Service HTTP

Aggiungere in `orders.service.ts` (o service API ordini):

```typescript
downloadOrderPdf(orderId: number): Observable<Blob> {
  return this.http.get(
    `${this.apiBase}/api/v1/orders/${orderId}/pdf`,
    { responseType: 'blob' }
  );
}
```

### 2) Handler UI (modale dettaglio ordine)

- Bottone toolbar **«Stampa ordine»** (icona `print`)
- Visibile se utente ha accesso ordini (route già protetta; opzionale check RBAC `orders.read`)
- On click:
  1. `loading = true`
  2. `downloadOrderPdf(selectedOrder.id_order)`
  3. On success: `URL.createObjectURL(blob)` → `window.open(url, '_blank')`
  4. Fallback se popup bloccato: `<a download="Ordine-{id}.pdf">`
  5. On error: parse blob JSON se 404/500, toast/Swal
  6. `loading = false` in `finalize`

**(Opzionale)** Auto-stampa come borderò: `win?.addEventListener('load', () => win.print())`

### 3) Error handling blob

Su `HttpErrorResponse` con `err.error instanceof Blob`, fare `await err.error.text()` + `JSON.parse` per leggere `detail`.

### 4) (Opzionale) Lista ordini

Voce menu contestuale «Stampa ordine» che riusa lo stesso handler passando `order.id_order`.

---

## Vincoli / non fare

- ❌ Non costruire template HTML stampa ordine lato FE
- ❌ Non usare `id_origin` nel path PDF
- ❌ Non fare GET ordine completo solo per stampare (il BE carica tutto)
- ❌ Non cambiare contratto API (layout PDF è server-side)

---

## File FE probabili da toccare

(adattare ai path reali del repo Angular)

| File | Modifica |
|------|----------|
| `src/app/core/services/orders.service.ts` | `downloadOrderPdf()` |
| `src/app/pages/orders/order-details-modal/order-details-modal.component.ts` | handler + loading |
| `src/app/pages/orders/order-details-modal/order-details-modal.component.html` | bottone toolbar |
| `src/app/pages/orders/order-list/order-list.component.ts` | (opz.) menu riga |

---

## Test manuali

1. Apri modale ordine con righe + spedizione → Stampa → PDF in nuova tab, layout completo.
2. Ordine con `general_note` → NOTE visibile in PDF.
3. Ordine inesistente (id fake) → messaggio errore.
4. Popup blocker attivo → download file funziona.

---

## Definition of done

- [ ] `downloadOrderPdf` nel service
- [ ] Bottone modale dettaglio funzionante
- [ ] Blob + nuova tab (o download fallback)
- [ ] Errori 404/500 gestiti
- [ ] Nessuna regressione su stampa preventivo/borderò

---

## Riferimento BE (solo lettura)

Repo: **ECommerceManagerAPI**  
Endpoint: `src/routers/order.py` → `download_order_pdf`  
PDF: `src/services/pdf/order_pdf_service.py`
