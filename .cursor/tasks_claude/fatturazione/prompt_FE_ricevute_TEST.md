# Prompt FE — Test integrazione Ricevute (BE pronto)

Incolla questo intero messaggio in chat sul **repo Angular del gestionale**.

---

## Contesto

Il backend **ECommerceManagerAPI** ha completato l’integrazione **Ricevute estero** (documenti fiscali interni, no SDI).  
Obiettivo di questa sessione: **testare end-to-end** quanto già integrato o da integrare sul FE, segnalare bug di contratto/UI, **non** implementare email (BE-2.6 stand-by).

Handoff BE: `docs/FE_HANDOFF_RICEVUTE.md` (nel repo API).  
Implementazione FE di riferimento: `prompt_FE_ricevute.md`.

---

## Prerequisiti BE (verificare prima dei test)

1. Migration eseguita sull’ambiente puntato dal FE:
   ```bash
   python scripts/migrations/create_ricevute_table.py
   ```
2. API up (es. `http://localhost:8000`) — Swagger tag **Ricevute**.
3. Utente JWT con permessi `fiscal_documents:read|create|update|delete`.
4. Almeno **un ordine idoneo**: estero/privato, **pagato**, **non fatturato**, **non** in Spedizione Confermata (`id_order_state !== 4`), senza ricevuta emessa già presente.

Se `GET /api/v1/ricevute` risponde **500** → quasi sempre tabella `ricevute` mancante lato BE.

---

## ⚠️ Contratto API v2 (breaking change — allineare modelli TS)

Il dettaglio ricevuta è **snellito**. Non usare più:

| ❌ Vecchio | ✅ Nuovo |
|-----------|---------|
| `detail.id_order` | `detail.order.id_order` |
| `detail.id_customer` | `detail.customer.id_customer` |
| `detail.righe` | `detail.order_details` |
| `detail.pdf_hash` | rimosso |
| `order.is_modifiable` | solo `detail.is_modifiable` |
| sempre `address_delivery` + `address_invoice` | sempre `address_delivery` + `address_invoice` (nullable; se uguali, stesso oggetto) |

Lista: resta `id_order`; **rimosso** `id_customer` in root (usare `customer.id_customer`).

---

## Endpoint da testare

Base: `/api/v1/ricevute` — header `Authorization: Bearer <JWT>`

| # | Metodo | Path | Cosa verificare |
|---|--------|------|-----------------|
| 1 | GET | `/ricevute?page=1&limit=10` | Lista paginata; `total`, filtri |
| 2 | GET | `/ricevute/{id}` | Dettaglio contratto v2 |
| 3 | POST | `/ricevute` `{ id_order, data_emissione? }` | 201 + PDF già generato |
| 4 | GET | `/ricevute/{id}/pdf` | Blob PDF in nuova tab |
| 5 | PUT | `/ricevute/{id}` `{ data_emissione }` | Data aggiornata + PDF rigenerato |
| 6 | DELETE | `/ricevute/{id}` | Soft delete → `stato: annullata` |
| 7 | GET | `/ricevute/{id}/export?fmt=csv` | Download CSV |
| 8 | GET | `/ricevute/{id}/export?fmt=xlsx` | Download Excel |
| 9 | GET | `/ricevute/export?fmt=xlsx&data_emissione_from=...` | Export massivo |
| 10 | GET | `/ricevute?id_order=X&stato=emessa` | Anti-duplicato da modale ordine |

**Non testare:** `POST .../invia-mail` (BE-2.6 non implementato).

---

## Scenari di test (checklist)

### A — Modelli e service

- [ ] Aggiornare `ricevuta.model.ts` al contratto v2 (`order_details`, embed snelli).
- [ ] `RicevuteService`: tutti i metodi chiamano gli URL corretti con `responseType: 'blob'` per PDF/export.
- [ ] Nessun riferimento residuo a `righe`, `pdf_hash`, `id_order`/`id_customer` in root del dettaglio.

### B — Lista ricevute

- [ ] Pagina/sezione lista carica senza errori (`total: 0` = OK).
- [ ] Filtri: `stato`, range `data_emissione`, `id_order`.
- [ ] Colonna numero: display **`{numero}/{anno}`** (es. `7/2026`).
- [ ] Click riga → dettaglio.

### C — Creazione da ordine

- [ ] Modale ordine: `GET ?id_order=X&stato=emessa` — se `total > 0` mostrare link a ricevuta esistente, **non** bottone Genera.
- [ ] POST creazione su ordine idoneo → 201 → redirect dettaglio o anteprima PDF.
- [ ] Verificare payload risposta: `order`, `customer`, `order_details[]`, `is_modifiable`.
- [ ] Indirizzo: sempre `address_delivery` e `address_invoice` (nullable; se consegna = fatturazione, stesso contenuto).

### D — Dettaglio

- [ ] Header: numero/anno, date incasso/emissione, stato, totali da `order`.
- [ ] Tabella prodotti da `order_details` (prezzi live).
- [ ] Link ordine via `order.id_order`.
- [ ] Cliente da `customer` (nome, email).

### E — PDF

- [ ] Download/apertura PDF dopo creazione (senza chiamata extra se già in POST).
- [ ] Rigenerazione: `GET .../pdf` se file mancante.

### F — Modifica e annullo

- [ ] PUT `data_emissione` → successo se `is_modifiable === true`.
- [ ] DELETE → `stato === 'annullata'`; bottoni disabilitati.
- [ ] Con `is_modifiable === false` (ordine spedito, `id_order_state === 4`): Modifica/Annulla **disabled** + tooltip.
- [ ] Con `stato === 'annullata'`: azioni disabilitate indipendentemente da `is_modifiable`.

### G — Export (BE-2.5)

- [ ] Export singola CSV/XLSX dal dettaglio — file scaricato con nome `Ricevuta-{numero}-{anno}.*`
- [ ] Export massivo con filtro date — file `ricevute-export-...`

### H — Errori attesi (400)

Verificare messaggio UI comprensibile:

- Ordine già con ricevuta emessa → POST bloccato.
- Ordine fatturato / non pagato / spedito → POST o PUT/DELETE bloccato.
- Formato export invalido → 400.

---

## Errori comuni

| Sintomo | Causa probabile |
|---------|-----------------|
| 500 su qualsiasi GET/POST ricevute | Tabella DB non migrata |
| Validation error su dettaglio | Modelli TS non allineati a v2 |
| PDF vuoto / errore | Ordine senza righe idonee |
| Bottoni modifica sempre attivi | Ignorato `is_modifiable` o `stato` |

---

## Output richiesto da questa sessione test

Al termine, produrre un **report breve** con:

1. **Pass/Fail** per ogni blocco A–H.
2. Screenshot o note su bug (endpoint, payload, messaggio errore).
3. Diff suggerito su modelli/service se il contratto non combacia.
4. Eventuali gap UX (non bloccare su export/email se non prioritari).

Non implementare BE-2.6 (email). Export e PDF sono in scope test.

---

## Riferimenti rapidi TypeScript (dettaglio)

```typescript
interface RicevutaDetail {
  id_ricevuta: number;
  numero: number;
  anno: number;
  data_incasso: string;
  data_emissione: string;
  stato: 'emessa' | 'annullata';
  is_modifiable: boolean;
  customer: { id_customer: number; firstname?: string; lastname?: string; email?: string } | null;
  order: {
    id_order: number;
    reference?: string | null;
    id_order_state: number;
    total_price_with_tax: number;
    // ...
  } | null;
  address_delivery: RicevutaAddress | null;
  address_invoice: RicevutaAddress | null;
  order_details: RicevutaOrderDetail[];
}
```

Permessi RBAC: stessi dei Corrispettivi (`fiscal_documents:*`).
