# Handoff FE — Fatture / NC di acquisto (ciclo passivo)

**Base URL:** `/api/v1/purchase-invoices`  
**Auth:** Bearer JWT  
**RBAC:** modulo `purchase_invoices` — `read` | `update` | `create` (solo sync)  
**Swagger:** tag **Purchase Invoices**

Documenti **ricevuti dai fornitori** (non le fatture emesse su `/fiscal_documents`, non le ricevute estero).

---

## Flusso UI suggerito

1. Sezione lista: tabella documenti (fatture TD01 + NC TD04)
2. Click riga → dettaglio con tabella prodotti/servizi (`details`)
3. Download XML
4. Select metodo pagamento (`GET /api/v1/payments/`) → salva come pagato
5. Opzionale: pulsante “Aggiorna ora” → `POST /sync` (lo scheduler gira già ogni 15 min)

---

## Endpoints

### GET `/api/v1/purchase-invoices/`

Query: `page`, `limit`, `is_paid`, `tipo_documento` (`TD01`|`TD04`), `date_from`, `date_to`, `q`

```json
{
  "items": [
    {
      "id": 1,
      "tipo_documento": "TD01",
      "numero_documento": "123/2026",
      "data_documento": "2026-07-15",
      "fornitore_denominazione": "Fornitore Test SpA",
      "fornitore_piva": "IT01234567890",
      "importo_totale": 1220.0,
      "fattura_collegata_numero": null,
      "fattura_collegata_data": null,
      "is_paid": false,
      "id_payment": null,
      "payment_name": null,
      "paid_at": null,
      "identificativo_sdi": "...",
      "nome_file": "..."
    }
  ],
  "total": 1,
  "page": 1,
  "limit": 20
}
```

La lista **non** include le righe.

### GET `/api/v1/purchase-invoices/{id}`

Come item lista + `note`, `details[]`:

```json
{
  "details": [
    {
      "numero_linea": 1,
      "descrizione": "Abbonamento hosting annuale",
      "codice_articolo": null,
      "quantita": 1.0,
      "unita_misura": null,
      "prezzo_unitario": 1000.0,
      "prezzo_totale": 1000.0,
      "aliquota_iva": 22.0,
      "natura": null
    }
  ]
}
```

Per le NC: usare `fattura_collegata_numero` / `fattura_collegata_data` in header.

### GET `/api/v1/purchase-invoices/{id}/xml`

Attachment `application/xml`.

### PATCH `/api/v1/purchase-invoices/{id}/payment`

```json
{ "is_paid": true, "id_payment": 3 }
```

```json
{ "is_paid": false }
```

Regole: se `is_paid=true` → `id_payment` obbligatorio; se `false` → azzera pagamento e `paid_at`.  
Metodi: `GET /api/v1/payments/`.

### POST `/api/v1/purchase-invoices/sync`

Trigger manuale; risposta con stats (`entries_saved`, `errors`, …).  
Permesso: `purchase_invoices:create`.

---

## Note

- Sync automatico: env `FATTURAPA_POOL_SYNC_*` (vedi `env.example` / `docs/FATTURAPA.md` §12)
- Distinguere in UI TD01 vs TD04 (badge / filtro)
- `descrizione` riga = prodotto o servizio fornitore (nessun match catalogo interno)
