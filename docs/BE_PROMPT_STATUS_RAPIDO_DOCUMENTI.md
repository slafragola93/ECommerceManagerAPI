# Stati rapidi documenti fiscali / ricevute / acquisti

**Stato BE:** implementato (2026-07-29; overlay SdI 2026-09-10)  
**Contratto FE colonna rapida:** `fatturapa_status` resta `uploaded|sent|error|null`. Overlay da `sdi_status` persistito: RC/MC/NE/DT → `sent`; NS → `error` (“Scartata da SDI”). Dettaglio timeline: `GET /api/v1/fiscal_documents/{id}/sdi-status`.

---

## Contesto

Colonna FE "Stato rapido" su:

- `GET /api/v1/fiscal_documents/` (+ dettaglio)
- `GET /api/v1/ricevute/` (+ dettaglio)
- `GET /api/v1/purchase-invoices/` (+ dettaglio)

Icone:

1. **Pagamento** → `is_payed` (fiscal/ricevute) o `is_paid` (purchase)
2. **Invio mail** → `mail_status`
3. **Esito FatturaPA / SdI** → `fatturapa_status` (workflow upload **oppure** overlay notifiche se `sdi_status` valorizzato)

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

Fonte: workflow interno + `upload_result`, **poi** overlay `fiscal_documents.sdi_status` se presente.  
Timeline completa: `GET /{id}/sdi-status`. Enum lista invariato: `uploaded|sent|error|null`.

| Valore | Significato |
|--------|-------------|
| `null` | Non applicabile / XML non ancora allo SdI (`pending`/`generated` senza notifica) |
| `uploaded` | Caricato su FatturaPA via API, senza invio SDI |
| `sent` | `status=sent` **oppure** `sdi_status` in consegnata/accettata/rifiutata/MC/DT **oppure** acquisto POOL |
| `error` | Errore FatturaPA / upload / validazione |

`fatturapa_error_message`: solo se `error`.  
`identificativo_sdi`: ID se noto (colonna persistita sul documento, POOL acquisti, o parse `upload_result`).

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

- Mostrare «Invia a SDI» (`send-to-sdi`) e «Reinvia dopo scarto» (`retry-send`).
- Tenere genera/scarica XML, PDF, `GET .../sdi-status`.
- Dopo NS: PATCH (stesso numero/data) + `retry-send`. Oppure `POST .../reset-xml` poi `retry-send`.
- Colonna rapida: binding `fatturapa_status` (non `sdi_status` grezzo).
- Icona esito: `uploaded` / `sent` = ok/in corso; `error` = KO (anche scarto SdI); `null` = grigio/N/A.
- Dettaglio timeline: `GET /api/v1/fiscal_documents/{id}/sdi-status` — non allargare l'enum `fatturapa_status`.
