# Prompt BE — Update Invoice + Sync Order (2026-07-28)

Copia tutto il contenuto **sotto la riga `---`** e incollalo in una nuova chat Cursor sul repository backend (**ECommerceManagerAPI**).

Obiettivo: introdurre un endpoint unico per aggiornare fattura (header + righe) e sincronizzare automaticamente l'ordine collegato in modo atomico.

---

## Contesto e problema

Nel FE, dal dettaglio fattura l'utente modifica righe/importi/sconti.
Ad oggi la modifica passa su `order_detail` e la fattura resta snapshot storico, creando incoerenza operativa:

- ordine aggiornato;
- documento fiscale collegato non allineato.

Richiesta contabilità: mantenere il flusso utente corrente (modifica da dettaglio fattura), ma con persistenza reale sulla fattura e aggiornamento automatico dell'ordine collegato.

## Endpoint richiesto

Implementare un endpoint unico:

```http
PATCH /api/v1/fiscal_documents/{id_fiscal_document}
```

Il backend deve accettare:

1. campi header documento (già supportati oggi);
2. aggiornamento righe fattura;
3. flag `sync_order` per riallineare automaticamente l'ordine collegato.

## Contratto payload proposto

```json
{
  "note": "string|null",
  "id_payment": 3,
  "payment_due_date": "2026-07-31",
  "shipping_total_price_net": 50.0,
  "shipping_total_price_with_tax": 61.0,
  "sync_order": true,
  "order_details": [
    {
      "id_order_detail": 1234,
      "product_name": "Prodotto",
      "product_reference": "SKU-1",
      "product_qty": 2,
      "product_weight": 1.2,
      "id_tax": 7,
      "unit_price_net": 100.0,
      "unit_price_with_tax": 122.0,
      "total_price_net": 180.0,
      "total_price_with_tax": 219.6,
      "reduction_percent": 10.0,
      "reduction_amount": 0.0,
      "note": "nota riga"
    }
  ]
}
```

Note:
- `sync_order` default `false` per retrocompatibilita.
- Se `order_details` non presente, comportamento corrente header-only.
- Se `sync_order=true` e `order_details` presenti, aggiornare anche righe ordine collegate.

## Esempio payload FE reale (pronto copia/incolla)

```json
{
  "id_fiscal_document": 1287,
  "sync_order": true,
  "header": {
    "note": "Aggiornamento condizioni commerciali",
    "default_note": false,
    "id_payment": 3,
    "is_payed": false,
    "payment_due_date": "2026-08-15",
    "shipping_total_price_net": 50.0,
    "shipping_total_price_with_tax": 61.0,
    "total_weight": 12.5,
    "id_carrier_api": 4,
    "id_tax": 7,
    "shipping_message": "Consegna in 48h"
  },
  "order_details": [
    {
      "id_order_detail": 5012,
      "product_name": "Climatizzatore a soffitto",
      "product_reference": "KIT-IF3-XY140T",
      "product_qty": 1,
      "product_weight": 8.4,
      "id_tax": 7,
      "unit_price_net": 2244.24,
      "unit_price_with_tax": 2737.97,
      "total_price_net": 2000.24,
      "total_price_with_tax": 2440.29,
      "reduction_percent": 0,
      "reduction_amount": 244.0,
      "note": "Sconto commerciale applicato"
    }
  ]
}
```

Nota operativa:
- nel transport HTTP il path resta `PATCH /fiscal_documents/{id_fiscal_document}`.
- il nodo `header` puo essere appiattito nei campi root se preferite mantenere retrocompatibilita piena con il `PATCH` corrente.

## Regole di business richieste

1. **Atomicita**:
   - update fattura + sync ordine nella stessa transazione DB;
   - se fallisce sync ordine, rollback update fattura.

2. **Vincoli stato documento**:
   - consentire update economico righe solo negli stati ammessi dal dominio (es. `pending`/`issued` se previsto);
   - se stato non ammesso -> errore 409/422 con messaggio esplicito.

3. **Validazioni importi/righe**:
   - qty > 0;
   - sconto percentuale 0..100;
   - sconto importo non oltre imponibile riga;
   - coerenza `unit_price_*`, `total_price_*`, `id_tax` (ricalcolo server-side autorevole).

4. **Sync ordine**:
   - aggiornare i `order_detail` collegati per `id_order_detail`;
   - riallineare totali ordine e campi derivati;
   - preservare policy fiscali esistenti (VIES, shipping, audit).

5. **Audit e tracciabilita**:
   - loggare operazione con correlation id unico;
   - distinguere nel log update fattura e update ordine nella stessa operazione.

## Response attesa

Restituire documento fiscale aggiornato nello stesso formato di:

```http
GET /api/v1/fiscal_documents/{id_fiscal_document}
```

Opzionale consigliato: metadato minimale su sync ordine, ad es.:

```json
{
  "sync_order_result": {
    "order_id": 55,
    "updated_lines": 3
  }
}
```

Esempio response completa suggerita:

```json
{
  "document": {
    "id_fiscal_document": 1287,
    "document_type": "invoice",
    "status": "pending",
    "id_order": 991,
    "total_price_net": 2050.24,
    "total_price_with_tax": 2501.29,
    "shipping_total_price_net": 50.0,
    "shipping_total_price_with_tax": 61.0,
    "order_details": [
      {
        "id_order_detail": 5012,
        "product_qty": 1,
        "id_tax": 7,
        "unit_price_net": 2244.24,
        "unit_price_with_tax": 2737.97,
        "total_price_net": 2000.24,
        "total_price_with_tax": 2440.29,
        "reduction_percent": 0,
        "reduction_amount": 244.0
      }
    ],
    "date_upd": "2026-07-28T10:30:11Z"
  },
  "sync_order_result": {
    "enabled": true,
    "order_id": 991,
    "updated_lines": 1,
    "status": "success"
  }
}
```

## Error model

Usare errori strutturati compatibili con FE:
- 422 validazione payload;
- 409 stato documento non aggiornabile;
- 404 documento o riga ordine non trovati;
- 500 solo per errori non gestiti.

Messaggi chiari e specifici (no errori generici).

## Checklist tecnica BE

- [x] Schema request aggiornato (Pydantic) con `sync_order` e `order_details`
- [x] Service transactionale update fattura + sync ordine
- [x] Validazioni dominio/documento + calcoli server-side
- [x] Endpoint PATCH aggiornato e documentato su OpenAPI
- [x] Test:
  - [x] update header-only (regressione)
  - [x] update righe + sync ordine success
  - [x] rollback in caso errore sync ordine
  - [x] stato non ammesso
  - [x] payload invalido

## Criteri di accettazione

1. Modificando sconto/qty/prezzo da FE su fattura:
   - la fattura risulta aggiornata al reload;
   - l'ordine collegato risulta coerente.
2. Nessun caso in cui ordine e fattura rimangano disallineati dopo esito 200.
3. Nessuna regressione su endpoint esistenti (`create`, `generate-xml`, `pdf`, `status`, `delete`).
