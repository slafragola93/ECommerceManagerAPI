# Prompt FE — Stati rapidi documenti (allineamento BE 2026-09-10)

Incolla questo intero messaggio in chat sul **repo Angular del gestionale**.

**Flusso operativo attuale (obbligatorio):** XML nel gestionale, invio via API (`send-to-sdi` / `retry-send`), esiti da `GET .../sdi-status`.  
Mostrare **Invia a SDI** e **Reinvia dopo scarto**.  
Dopo NS: PATCH (stesso numero/data) + `POST .../retry-send`. `POST .../reset-xml` elimina l’XML e torna `pending`.  
`fatturapa_status` in lista: `sent` se RC/MC/NE/DT; `error` se NS.  
Lista: usare anche `sdi_status` e `order_payment_name` sullo stesso GET (niente N GET).

---

## Contesto

Il backend **ECommerceManagerAPI** ha esposto i campi **stato rapido** (colonna icone a sinistra) su lista e dettaglio di:

| Sezione | Endpoint lista | Endpoint dettaglio |
|---------|----------------|--------------------|
| Fatture / NC emesse | `GET /api/v1/fiscal_documents/` | `GET /api/v1/fiscal_documents/{id}` |
| Ricevute | `GET /api/v1/ricevute/` | `GET /api/v1/ricevute/{id}` |
| Fatture / NC acquisto | `GET /api/v1/purchase-invoices/` | `GET /api/v1/purchase-invoices/{id}` |

Doc BE: `docs/BE_PROMPT_STATUS_RAPIDO_DOCUMENTI.md` (repo API).

**Obiettivo sessione:** allineare modelli TypeScript, mapping icone e tooltip al contratto BE **reale**. Eliminare euristiche FE e il draft `sdi_status` / `accepted|rejected`.

---

## Breaking vs draft FE precedente

| Draft FE (da scartare) | Contratto BE attuale |
|------------------------|----------------------|
| `sdi_status` | **`fatturapa_status`** |
| `sdi_error_message` | **`fatturapa_error_message`** |
| Enum `accepted \| pending \| rejected` | Enum **`uploaded \| sent \| error \| null`** |
| Euristiche su `status` grezzo | Usare solo i campi sotto |

Motivo naming: l’enum lista resta `fatturapa_status`. Overlay BE da `sdi_status` persistito (RC/MC/NE/DT → `sent`; NS → `error`). Timeline completa: `GET /api/v1/fiscal_documents/{id}/sdi-status`.

---

## Contratto comune (lista + dettaglio)

Ogni item espone:

```ts
interface DocumentQuickStatus {
  mail_status: 'sent' | 'pending' | 'error' | null;
  mail_error_message: string | null;
  fatturapa_status: 'uploaded' | 'sent' | 'error' | null;
  fatturapa_error_message: string | null;
  identificativo_sdi: string | null;
}
```

### Pagamento (icona 1)

| Risorsa | Campo | Note |
|---------|-------|------|
| fiscal_documents | `is_payed: boolean` | **Ora anche in lista** (prima solo dettaglio arricchito) |
| ricevute | `is_payed: boolean` | **Ora anche in lista** |
| purchase-invoices | `is_paid: boolean` | Già presente |

Non unificare i nomi lato BE; nel FE mappare a un unico `isPaid` interno se serve.

### Mail (icona 2)

| Valore | UI suggerita |
|--------|----------------|
| `null` | icona neutra / “non inviata” (stato attuale di default) |
| `pending` | in corso |
| `sent` | ok |
| `error` | ko + tooltip `mail_error_message` |

Oggi BE restituisce quasi sempre `null` (invio mail documento non ancora implementato). **Non inventare** lo stato dalla presenza email cliente.

### Esito FatturaPA (icona 3)

| Valore | Significato | UI suggerita |
|--------|-------------|--------------|
| `null` | N/A (ricevute; doc non elettronico; non ancora caricato) | grigio / nascosta o “—” |
| `uploaded` | Su FatturaPA, non inviato a SDI | ok “caricata” / warning soft |
| `sent` | Inviata a SDI (API o notifica RC/MC/NE/DT) **oppure** ricevuta da POOL | ok |
| `error` | Errore FatturaPA **oppure** scarto SdI (NS) | ko + tooltip `fatturapa_error_message` |

`identificativo_sdi`: mostrare in tooltip/dettaglio se valorizzato; **non** usarlo come unico segnale di stato (usa `fatturapa_status`).

---

## Comportamento per sezione

### Fatture / NC (`fiscal_documents`)

- Lista: binding su `documents[]` (o nome usato dal FE) con i nuovi campi + `is_payed`.
- Dettaglio invoice/NC v3: stessi campi quick-status.
- Mapping tipico BE: `status=uploaded` → `uploaded`; `sent` → `sent`; `error` → `error`. Overlay: `sdi_status` emesso → `sent`; `scartata` → `error`. `pending`/`generated` senza notifica → `null`.

### Ricevute

- `fatturapa_status`, `fatturapa_error_message`, `identificativo_sdi` → **sempre `null`** (no SDI).
- Icona esito FatturaPA: sempre N/A (o nascondere).
- Usare `is_payed` in lista.

### Purchase invoices

- Se c’è `identificativo_sdi` → BE setta `fatturapa_status: "sent"`.
- Pagamento: `is_paid` (non `is_payed`).

---

## Task FE

1. Aggiornare `*.model.ts` / interfacce per le 3 liste + dettagli.
2. Rimuovere tipi/enum `SdiStatus`, `accepted`, `rejected` legati allo stato rapido.
3. Aggiornare componente colonna “Stato rapido” (3 icone) per leggere solo i campi BE.
4. Tooltip errori: `mail_error_message` / `fatturapa_error_message` solo se status = `error`.
5. Eliminare fallback euristici su `status`, `upload_result`, presenza XML, ecc. per queste icone.
6. Smoke test:
   - lista fatture: `pending`/`generated` senza notifica → esito null; NS → `error`; RC/MC → `sent`
   - lista ricevute: esito sempre N/A; pagamento da `is_payed`
   - lista acquisti: con SDI id → esito `sent`

---

## Esempio payload lista fiscal

```json
{
  "id_fiscal_document": 123,
  "document_number": "000042",
  "status": "uploaded",
  "is_electronic": true,
  "is_payed": true,
  "mail_status": null,
  "mail_error_message": null,
  "fatturapa_status": "uploaded",
  "fatturapa_error_message": null,
  "identificativo_sdi": null
}
```

## Esempio errore

```json
{
  "is_payed": false,
  "mail_status": null,
  "mail_error_message": null,
  "fatturapa_status": "error",
  "fatturapa_error_message": "Errore upload a FatturaPA: ...",
  "identificativo_sdi": null
}
```

---

## Fuori scope

- Implementare invio mail documento (BE non espone ancora writer; campi pronti).
- Timeline notifiche: `GET /fiscal_documents/{id}/sdi-status` (dettaglio). In lista l’overlay è già in `fatturapa_status`.
- Dopo NS: PATCH + `retry-send`. Mail cortesia fuori scope.

---

## Done criteria

- [ ] Nessun riferimento FE a `sdi_status` / `accepted` / `rejected` per la colonna stato rapido
- [ ] Binding corretto `fatturapa_*` + `mail_*` + `is_payed`/`is_paid` sulle 3 liste
- [ ] Tooltip errori solo su `error`
- [ ] Ricevute: icona FatturaPA sempre N/A
- [ ] Nessuna euristica su campi grezzi per queste 3 icone
