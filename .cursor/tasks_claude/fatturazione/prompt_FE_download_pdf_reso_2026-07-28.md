# Prompt FE — Download PDF reso

Copia-incolla in chat Cursor sul repo Angular.

---

## Task

Aggiungere in UI (lista/dettaglio reso) il download/stampa PDF del reso, allineato al pattern già usato per ordine / fattura / ricevuta.

## Endpoint BE (già pronto)

```
GET /api/v1/orders/returns/{id_fiscal_document}/pdf
```

| Voce | Valore |
|------|--------|
| Auth | Bearer JWT |
| Permesso | `returns:read` |
| Response | `application/pdf` |
| Content-Disposition | `inline; filename="reso-{document_number}.pdf"` |
| 404 | reso inesistente / non è un `return` / nessuna riga |

`id_fiscal_document` = ID reso (stesso usato in `GET .../returns/get-return-by-id/{id}`).

## Implementazione suggerita

1. Service/API: metodo `downloadReturnPdf(idFiscalDocument)` → `blob` (`responseType: 'blob'`).
2. UI: bottone **PDF** / **Stampa** su dettaglio reso (e opzionale in lista).
3. Aprire in nuova tab o trigger download:
   - `URL.createObjectURL(blob)` + `window.open` / `<a download>`
   - filename da `Content-Disposition` se disponibile, fallback `reso-{id}.pdf`
4. Disabilitare/nascondere se l’utente non ha `returns:read`.
5. Toast/errore su 404/500 (messaggio da body se JSON, altrimenti generico).

## Riuso

Copiare il flusso già usato per:
- `GET /api/v1/orders/{id}/pdf`
- `GET /api/v1/fiscal_documents/{id}/pdf`
- `GET /api/v1/ricevute/{id}/pdf`

Stesso pattern blob + inline preview.

## Acceptance

- [ ] Dal dettaglio reso si apre/scarica il PDF
- [ ] Nome file sensato (`reso-…pdf`)
- [ ] Errore gestito se reso non trovato
- [ ] Nessuna regressione su PDF ordine/fattura/ricevuta
