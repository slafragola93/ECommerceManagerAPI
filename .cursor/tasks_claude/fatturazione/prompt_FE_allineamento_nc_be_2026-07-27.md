# Prompt FE — Allineamento BE note di credito (2026-07-27)

Copia tutto il contenuto **sotto la riga `---`** e incollalo in una nuova chat Cursor sul **repository del gestionale Angular**.

Handoff BE (repo **ECommerceManagerAPI**):

- Doc: [`docs/FATTURAPA.md`](../../../docs/FATTURAPA.md) §8 Note di credito
- Prompt base (contratto v3, export): [`prompt_FE_nota_credito_parziale.md`](./prompt_FE_nota_credito_parziale.md)

**Obiettivo sessione:** verificare e allineare il FE alle modifiche BE del 2026-07-27 su creazione NC e XML TD04. Non rifare il contratto v3 se già allineato: concentrarsi su **validazione parziale** e **comportamenti XML/UX**.

---

## Contesto BE (cosa è cambiato)

| Area | Prima (rischio) | Ora (BE) |
|------|-----------------|----------|
| NC parziale senza `items` | Accettata → storno residuo **totale** ma `is_partial=true` (201 silenzioso) | **422** se `is_partial=true` **senza** items e **senza** spedizione. Consentito: solo spedizione (`include_shipping=true` + `items` vuoti) |
| XML TD04 + coupon ordine | Riga “Buoni Sconto” da `order.total_discounts` anche sulle NC → totali incoerenti | TD04 **non** emette più quella riga; TD01 invariato |
| XML TD04 scadenza | Poteva uscire `DataScadenzaPagamento` &lt; Data NC | Default: tag **omesso** sulle NC; se presente, ≥ Data documento |
| XML TD04 | — | Sempre `DatiFattureCollegate`; filename `IT{piva}_{progressivo}.xml` (no `ITIT`) |

Endpoint creazione (invariato path):

```http
POST /api/v1/fiscal_documents/credit-notes
```

```json
{
  "id_invoice": 62,
  "reason": "Reso parziale",
  "is_partial": true,
  "include_shipping": false,
  "items": [{ "id_order_detail": 456, "quantity": 2 }]
}
```

Pre-submit righe eleggibili:

```http
GET /api/v1/fiscal_documents/{id_invoice}/details-with-products
```

Generazione XML (stesso flusso fattura):

```http
POST /api/v1/fiscal_documents/{id_nc}/generate-xml
```

Errori validazione body: **422** (Pydantic). Messaggio tipico se manca `items`: contiene `items` / `is_partial`.

---

## Cosa deve fare il FE

### 1. Modale / form NC parziale (priorità alta)

- [ ] Se l’utente sceglie **NC parziale prodotti**, il submit è disabilitato finché non c’è **almeno una riga** con `quantity > 0`
- [ ] Se l’utente sceglie **solo spedizione** (`include_shipping=true`, nessuna riga prodotto): **consentito** inviare `items: []` o omettere `items` con `is_partial: true`
- [ ] Non inviare `is_partial: true` con `items` vuoti **e** `include_shipping: false` (BE → 422)
- [ ] Ogni item prodotto: `id_order_detail` + `quantity` ≤ `remaining_qty`
- [ ] Mostrare errore utente-friendly se BE risponde 422
- [ ] NC **totale**: `is_partial: false` senza `items` — ok

Payload NC **solo spedizione**:

```json
{
  "id_invoice": 62,
  "reason": "Rimborso spese di spedizione",
  "is_partial": true,
  "include_shipping": true,
  "items": []
}
```

Esempio guard TypeScript (adattare al service esistente):

```typescript
function buildCreditNotePayload(form: {
  idInvoice: number;
  reason: string;
  isPartial: boolean;
  includeShipping: boolean;
  selected: { idOrderDetail: number; quantity: number }[];
}) {
  if (form.isPartial) {
    const items = form.selected.filter((r) => r.quantity > 0);
    if (items.length === 0 && !form.includeShipping) {
      throw new Error(
        'Seleziona almeno una riga da stornare oppure abilita il rimborso spedizione'
      );
    }
    return {
      id_invoice: form.idInvoice,
      reason: form.reason.trim(),
      is_partial: true,
      include_shipping: form.includeShipping,
      items: items.map((r) => ({
        id_order_detail: r.idOrderDetail,
        quantity: r.quantity,
      })),
    };
  }
  return {
    id_invoice: form.idInvoice,
    reason: form.reason.trim(),
    is_partial: false,
    include_shipping: form.includeShipping,
  };
}
```

### 2. Tipi / OpenAPI client

- [ ] Aggiornare tipi generati o interfacce create-NC: documentare che `items` è **required when `is_partial === true`**
- [ ] Non tipizzare `items` come sempre opzionale senza vincolo condizionale (commento JSDoc o type narrowing)

### 3. XML / export NC (verifica UX, non riscrivere XML)

Il FE non genera l’XML: lo fa il BE. Allineare eventuali copy/help e smoke test:

- [ ] Dopo `generate-xml` su NC, se la UI mostra/scarica XML o ZIP export: **non** aspettarsi riga “Buoni Sconto” da coupon ordine
- [ ] Non mostrare messaggi del tipo “scadenza pagamento NC = data fattura + 30gg” se presenti in UI/help
- [ ] Export `document_type=credit_note&fmt=xml`: ZIP può essere **parziale** (header `X-Export-Partial`, file `export-scarti.json`) — gestire come già sulle fatture se supportato
- [ ] Filename atteso nei download singoli/ZIP: `IT{11cifre}_{progressivo}.xml` (mai `ITIT…`)

### 4. Cosa **non** cambiare

- Contratto response v3 (`FiscalDocumentDetail` / `InvoiceDetail`) — già definito nel prompt base
- Path API create / details-with-products / generate-xml / export
- Logica IVA VIES / N3.2 (solo BE)

---

## Checklist test manuali FE

### Creazione NC

1. Fattura con ≥1 riga residua → modale NC **parziale prodotti** → conferma **senza** selezione e **senza** spedizione → blocco FE (o 422)
2. Seleziona 1 riga, qty valida → **201**, dettaglio con `is_partial=true` e `order_details` coerenti
2b. Solo toggle spedizione, nessuna riga → `is_partial=true`, `include_shipping=true`, `items=[]` → **201**, totali = solo spedizione, `order_details` prodotti vuoti (eventuale riga shipping sintetica in GET dettaglio)
3. NC **totale** senza items → **201**, `is_partial=false`
4. Network: POST `is_partial:true` + `include_shipping:false` senza `items` → **422** leggibile

### XML / export (opzionale ma consigliato)

5. Ordine **con coupon** → fattura → NC → Genera XML → apri XML: assente `Descrizione` = `Buoni Sconto`
6. Stesso ordine, XML fattura TD01: può ancora contenere Buoni Sconto (ok)
7. XML NC: presente `DatiFattureCollegate`; assente (di default) `DataScadenzaPagamento`
8. Export lista NC `fmt=xml` → ZIP scaricabile; se alcuni doc falliscono, UI non deve trattare tutto come fallimento se BE restituisce ZIP parziale

### Regressione

9. Dettaglio NC: stessi blocchi fattura + motivo + link fattura ref
10. PDF NC e send-to-sdi: stessi bottoni del flusso fattura sull’`id` NC

---

## Criterio “done”

- Impossibile (o chiaramente bloccato) creare NC parziale senza righe dal FE
- 422 BE su `items` gestito in UI
- Nessuna assunzione FE che l’XML NC includa i buoni carrello dell’ordine
- Smoke create + generate-xml/export NC ok su ambiente collegato al BE aggiornato
