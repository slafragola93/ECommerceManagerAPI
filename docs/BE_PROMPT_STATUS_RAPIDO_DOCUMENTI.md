# Stati rapidi documenti fiscali / ricevute / acquisti

**Stato BE:** implementato (2026-07-29)  
**Contratto FE:** campi sotto — **non** usare più `sdi_status` / `accepted|rejected` del draft iniziale.

---

## Contesto

Colonna FE "Stato rapido" su:

- `GET /api/v1/fiscal_documents/` (+ dettaglio)
- `GET /api/v1/ricevute/` (+ dettaglio)
- `GET /api/v1/purchase-invoices/` (+ dettaglio)

Icone:

1. **Pagamento** → `is_payed` (fiscal/ricevute) o `is_paid` (purchase)
2. **Invio mail** → `mail_status`
3. **Esito FatturaPA** → `fatturapa_status` (esito intermediario, non notifiche SDI RC/NS)

---

## Contratto comune (lista + dettaglio)

```json
{
  "mail_status": "sent|pending|error|null",
  "mail_error_message": "string|null",
  "fatturapa_status": "uploaded|sent|error|null",
  "fatturapa_error_message": "string|null",
  "identificativo_sdi": "string|null"
}
```

### Semantica `fatturapa_status`

Fonte: workflow interno + risposta **FatturaPA.com** (`status` / `upload_result`).  
Non è ancora il flusso completo notifiche SdI (backlog P0-03).

| Valore | Significato |
|--------|-------------|
| `null` | Non applicabile / non ancora caricato (ricevuta; doc non elettronico; `pending`/`generated`) |
| `uploaded` | Caricato su FatturaPA, senza invio SDI |
| `sent` | Inoltrato a SDI via FatturaPA (ciclo attivo) **oppure** ricevuto via POOL (acquisti con ID SDI) |
| `error` | Errore FatturaPA / upload / validazione |

`fatturapa_error_message`: solo se `error`.  
`identificativo_sdi`: ID se noto (POOL acquisti o parse `upload_result`).

### Semantica `mail_status`

| Valore | Significato |
|--------|-------------|
| `null` | Non inviata / non tracciata (default attuale) |
| `sent` / `pending` / `error` | Quando esisterà invio mail documento |

Colonne DB: `mail_status`, `mail_error_message` su `fiscal_documents`, `ricevute`, `fatture_acquisto_sync`.

### Pagamento in lista

- Fiscal list: `is_payed` (da ordine, batch)
- Ricevute list: `is_payed` (da ordine)
- Purchase list: `is_paid` (già presente)

---

## Mapping fiscal (ciclo attivo)

| Condizione | `fatturapa_status` |
|------------|--------------------|
| `is_electronic=false` | `null` |
| `status` in pending, generated, issued | `null` |
| `status=uploaded` | `uploaded` |
| `status=sent` | `sent` |
| `status=error` | `error` |

## Ricevute

`fatturapa_*` e `identificativo_sdi` sempre `null`.

## Purchase invoices

Se `identificativo_sdi` valorizzato → `fatturapa_status=sent`; altrimenti `null`.

---

## Codice

| Pezzo | Path |
|-------|------|
| Mapper | `src/services/documents/quick_status.py` |
| Schema mixin | `src/schemas/document_quick_status_schema.py` |
| Lista fiscal | `src/services/documents/fiscal_list_serializer.py` |
| Migration mail | `scripts/migrations/add_document_mail_quick_status.py` |

```powershell
python scripts/migrations/add_document_mail_quick_status.py
pytest tests/unit/services/documents/test_quick_status.py -v
```

---

## Note FE

- Rinominare binding da `sdi_status` → `fatturapa_status`.
- Icona esito: `uploaded` / `sent` = ok/in corso a seconda UX; `error` = KO; `null` = grigio/N/A.
- Estensione futura (notifiche RC/NS): possibili nuovi valori enum senza rompere i tre attuali.
