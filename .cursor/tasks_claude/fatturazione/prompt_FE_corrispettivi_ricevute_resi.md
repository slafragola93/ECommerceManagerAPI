# Prompt sessione FE — Corrispettivi, Ricevute, Resi (allineamento BE 2026-07-15)

Copia tutto il contenuto **sotto la riga `---`** e incollalo in una nuova chat Cursor sul **repository del gestionale Angular**.

**Prerequisiti BE (obbligatori su dev/staging):**
- Tabella `ricevute` migrata (`python scripts/migrations/create_ricevute_table.py` + `alter_ricevute_data_emissione_datetime.py` se non già fatto)
- API BE aggiornata con BE-3.1 / BE-3.2 / BE-3.3 corrispettivi + ricevute
- Swagger: `http://<BE_HOST>/docs` → tag **Corrispettivi**, **Ricevute**, **Resi**

**Documentazione BE (fonte di verità):**
- Corrispettivi: `docs/CORRISPETTIVI.md` (repo BE)
- Ricevute: `docs/FE_HANDOFF_RICEVUTE.md` (repo BE)
- Test BE: 91 test automatici su corrispettivi/ricevute/resi (unit + integration API)

---

## Obiettivo sessione FE

Allineare **UI, modelli TypeScript, servizi HTTP e flussi amministrativi** per tre aree collegate:

| Modulo | Route API | Permesso RBAC |
|--------|-----------|---------------|
| **Corrispettivi** | `/api/v1/corrispettivi` | `fiscal_documents:read` |
| **Ricevute estero** | `/api/v1/ricevute` | `fiscal_documents:read/create/update/delete` |
| **Resi ordine** | `/api/v1/orders/{id}/returns`, `/api/v1/orders/returns/` | `returns:read/create/update/delete` |

I corrispettivi sono **report live** (nessuno snapshot): ogni GET ricalcola da ordini, resi e ricevute. Il FE deve spiegare all’utente che i totali possono cambiare se fatturo/ricevuta/reso vengono modificati **a posteriori**.

---

## 1. Corrispettivi — cosa cambia in UI

### 1.1 Schermata principale → `GET /api/v1/corrispettivi/riepilogo`

Usare **`/riepilogo`** come tabella matriciale (giorni × aliquote IVA).

**Breaking / refactor UI (2026-07-15):**
- Importi **sempre con IVA inclusa** (non imponibile netto in questa vista)
- Per ogni aliquota, **4 metriche** in cella:
  - `products_sales` (entrate prodotti) → verde
  - `shipping_sales` (entrata spedizione) → verde
  - `products_returns` (resi prodotti) → rosso
  - `shipping_returns` (resi spedizione) → rosso
- Colonna/totale riga: `row_total` = vendite − resi (prodotti + spedizione)
- **Tutti i giorni del mese** (01..ultimo) anche a zero — non filtrare lato FE
- `columns[]` definisce ordine e label aliquote (`label` es. `"22"`, `"0"`, `"SPF"`)
- `cells[String(id_tax)]` — se chiave assente → quattro zeri
- Footer: `month_totals` con stessa struttura + `row_total`

**Filtri query (identici su riepilogo, summary, export):**

| Parametro | UI suggerita |
|-----------|--------------|
| `year`, `month` | Selettore anno + mese (un solo mese per richiesta) |
| `id_platform` | Dropdown canale (opzionale) |
| `id_store` | Dropdown conto/negozio (opzionale) |
| `delivery_country_iso` | Dropdown paese consegna ISO (opzionale) |
| `day` | Filtro giorno singolo (opzionale) |

### 1.2 Pannello audit ricevute → `GET /api/v1/corrispettivi/` (summary giornaliero)

Usare per **KPI / card / drawer audit** (non sostituisce la matrice `/riepilogo`).

Campo chiave: `days[].sales_breakdown` (BE-3.2), presente solo su giorni con movimenti ricevuta differita:

```typescript
interface CorrispettivoSalesBreakdown {
  base: CorrispettivoSplitTotals;              // vendite standard
  ricevute_decurtazione: CorrispettivoSplitTotals;  // negativo su date ordine
  ricevute_imputazione: CorrispettivoSplitTotals;   // positivo su data emissione
}
```

**UI consigliata:** tooltip o riga espandibile sul giorno con breakdown:
- **Vendite base**
- **Ricevute decurtazione** (lordo negativo)
- **Ricevute imputazione** (lordo positivo)
- Netto giorno = somma dei tre (+ resi separati in blocco `returns`)

**Regola amministrativa da mostrare in help/testo:**
- Se **giorno ordine = giorno emissione ricevuta** → tutto resta in **base** (nessun aggiustamento)
- Se **giorni diversi** → decurtazione sul **giorno ordine**, imputazione sul **giorno emissione**
- `data_incasso` ricevuta è **solo audit** — non usare in UI corrispettivi

**Nota:** `/riepilogo` = lordo con IVA per aliquota; `/` summary = lordo + netto + split prodotti/spedizione. Non mescolare le due semantiche nella stessa colonna.

### 1.3 Export → `POST /api/v1/corrispettivi/export`

Body:
```json
{ "year": 2026, "month": 7, "filters": { "id_store": 1, "delivery_country_iso": null } }
```

Response: blob ZIP `Registri.zip` con:
- `registro.xlsx` — consolidato (matrice aliquote, tutti i giorni)
- `registro_{ISO}.xlsx` — uno per paese con movimenti

**FE:**
- Stessi filtri della schermata (tranne: il consolidato **ignora** `delivery_country_iso` nel body export — inviare filtri UI ma il BE genera comunque il totale globale)
- Download via `responseType: 'blob'`
- **Non** aspettarsi colonne breakdown ricevute nell’Excel (solo su GET summary API)

### 1.4 Messaggistica utente (corrispettivi)

Mostrare banner/info permanente:
> I corrispettivi sono calcolati in tempo reale. Fatturare un ordine, emettere/eliminare una ricevuta o registrare/eliminare un reso **modifica i totali** dei mesi già consultati.

---

## 2. Ricevute estero — cosa cambia in UI

### 2.1 Stato BE (completo salvo email)

| Feature | Stato | Note FE |
|---------|-------|---------|
| Lista / dettaglio / creazione / PDF | ✅ | Integrare |
| PUT data emissione | ✅ | ISO datetime; rigenera PDF |
| DELETE | ✅ | **204** — cancellazione **definitiva** (non più soft delete `annullata`) |
| Export CSV/XLSX | ✅ | singola + massiva |
| Email PDF | ⏳ | non implementare |
| Blocco Spedizione Confermata | ❌ rimosso | BE **non blocca** POST/PUT/DELETE se `id_order_state === 4` |

### 2.2 `is_modifiable` — solo warning UX

| `is_modifiable` | Significato |
|-----------------|-------------|
| `true` | Ordine non in Spedizione Confermata |
| `false` | Ordine evaso (`id_order_state === 4`) |

**Implementazione FE:**
- **Non disabilitare** bottoni Modifica/Elimina solo per questo flag (salvo policy interna)
- Mostrare **dialog di conferma** esplicito se `is_modifiable === false`
- Dopo DELETE: l’ordine può ricevere una **nuova** ricevuta; i corrispettivi tornano al flusso vendite standard

### 2.3 Creazione da modale ordine

```http
POST /api/v1/ricevute
{ "id_order": 45001, "data_emissione": "2026-07-08T14:30:00" }
```

- `data_emissione` opzionale — accetta `YYYY-MM-DD` o ISO datetime (Europe/Rome)
- Errori **400**: ordine già fatturato, ricevuta già presente, ordine non pagato
- Dopo **201**: aprire dettaglio o anteprima PDF (già generato)

**Impatto corrispettivi (spiegare in modale):**
- Emissione **stesso giorno** dell’ordine → nessuno spostamento in corrispettivi
- Emissione **in giorno diverso** → incasso spostato nel corrispettivo (decurtazione/imputazione)

### 2.4 Modifica data emissione

```http
PUT /api/v1/ricevute/{id}
{ "data_emissione": "2026-07-10T09:15:00" }
```

- Rigenera PDF
- **Invalidare/refetch** corrispettivi del mese ordine e mese nuova emissione se la schermata corrispettivi è aperta (o toast «Ricalcolare corrispettivi»)

### 2.5 Dettaglio — contratto v2

- `order_details[]` live (+ riga `is_shipping: true` se presente)
- Sempre `address_delivery` e `address_invoice` (nullable)
- Numero documento: **`{numero}/{anno}`**
- `data_emissione` in lista/dettaglio: **ISO 8601 con ora**

### 2.6 Export ricevute (BE-2.5)

```http
GET /api/v1/ricevute/{id}/export?fmt=csv|xlsx
GET /api/v1/ricevute/export?fmt=xlsx&data_emissione_from=...&data_emissione_to=...
```

Permesso: `fiscal_documents:read`.

---

## 3. Resi ordine — cosa cambia in UI

### 3.1 API invariate, impatto corrispettivi da comunicare

| Azione | Endpoint | Effetto corrispettivi |
|--------|----------|------------------------|
| Crea reso | `POST /api/v1/orders/{id_order}/returns` | Movimento negativo alla **data documento reso** |
| Elimina reso | `DELETE /api/v1/orders/returns/{id}` | Reso sparisce al prossimo GET corrispettivi |
| Reso + ricevuta stesso ordine | — | **Indipendenti**: ricevuta agisce su vendite, reso su `returns_*` |

**Regole eligibilità (help testo):**
- Reso su ordine **non fatturato** e pagato → sì
- Reso su ordine **fatturato** → solo se esiste **nota di credito**
- Ordine non pagato → non compare nei corrispettivi (né vendite né resi)

### 3.2 UX post-azione

Dopo **creazione** o **eliminazione** reso:
- Toast: «I corrispettivi del mese sono stati aggiornati» + link «Vai ai corrispettivi» (opzionale)
- Se modale ordine mostra badge corrispettivi → refetch lazy

### 3.3 Lista resi

```http
GET /api/v1/orders/returns/?page=1&limit=10
GET /api/v1/orders/{id_order}/returns
GET /api/v1/orders/returns/get-return-by-id/{id_fiscal_document}
```

Permesso: `returns:read`.

---

## 4. Flusso amministrativo end-to-end (wireframe logico)

```
Ordine estero pagato (no fattura)
    ├─► [Opzionale] Emetti ricevuta (POST /ricevute)
    │       └─► Corrispettivi: base OPPURE decurtazione/imputazione
    ├─► [Opzionale] Registra reso (POST /orders/{id}/returns)
    │       └─► Corrispettivi: returns_* alla data reso
    └─► Consulta corrispettivi mese (GET /riepilogo + audit GET /)
            └─► Export ZIP commercialista (POST /export)
```

**Scenario combinato:** ordine con ricevuta differita + reso → entrambi visibili nei giorni corretti; eliminare il reso non tocca l’aggiustamento ricevuta.

---

## 5. Task FE suggeriti (checklist implementazione)

### Corrispettivi
- [ ] Refactor tabella `/riepilogo`: 4 voci per aliquota + `row_total`, importi lordi IVA
- [ ] Render **tutti i giorni** del mese (zeri inclusi)
- [ ] Filtri: anno, mese, canale, store, paese, giorno
- [ ] Pannello/summary con `GET /` + `sales_breakdown` (audit ricevute)
- [ ] Export ZIP con stessi filtri
- [ ] Banner «dati live / retroattività»
- [ ] NgRx/effects: stati loading/error; invalidazione cache al cambio mese/filtri

### Ricevute
- [ ] Verificare DELETE → gestione **204** (non aspettarsi body)
- [ ] Dialog conferma se `!is_modifiable` su PUT/DELETE
- [ ] Datepicker emissione con **ora** (ISO 8601)
- [ ] Help testo impatto corrispettivi in modale creazione/modifica
- [ ] Export CSV/XLSX lista e dettaglio
- [ ] Link ordine ↔ ricevuta ↔ corrispettivi (navigazione contestuale)

### Resi
- [ ] Toast/link post create/delete verso corrispettivi
- [ ] Help eligibilità (fattura / nota credito / pagato)
- [ ] Verificare totali reso coerenti con corrispettivi (QA)

### Modelli TypeScript
- [ ] Aggiornare/creare `corrispettivo.model.ts` da schemi in `docs/CORRISPETTIVI.md` §4
- [ ] Allineare `ricevuta.model.ts` (datetime emissione, DELETE definitivo)
- [ ] Permessi guard: `fiscal_documents:*`, `returns:*`

---

## 6. QA FE — scenari obbligatori

| # | Scenario | Atteso |
|---|----------|--------|
| 1 | Ordine IT pagato senza fattura | Compare in corrispettivi giorno `date_add` |
| 2 | Ricevuta same-day | Solo `base` in breakdown; nessun aggiustamento |
| 3 | Ricevuta emissione ≠ giorno ordine | Decurtazione giorno ordine + imputazione giorno emissione |
| 4 | DELETE ricevuta | Ordine torna in vendite base; corrispettivi aggiornati |
| 5 | Reso su ordine non fatturato | `products_returns` / `shipping_returns` giorno reso |
| 6 | DELETE reso | Reso sparisce da corrispettivi |
| 7 | Reso + ricevuta stesso ordine | Entrambi nei giorni corretti |
| 8 | Fattura ordine mese precedente | Ordine esce da corrispettivi mese ordine (live) |
| 9 | Filtro paese IT vs FR | Totali `/riepilogo` separati; export `registro_IT.xlsx` coerente |
| 10 | Export ZIP | `registro.xlsx` + almeno un `registro_{ISO}.xlsx` |

Prompt test automatizzati FE (opzionale): estendere `.cursor/tasks_claude/fatturazione/prompt_FE_ricevute_TEST.md` con casi corrispettivi.

---

## 7. Non fare (fuori scope BE attuale)

- UI invio email ricevuta (BE-2.6)
- Persistenza/snapshot corrispettivi lato FE (i totali sono sempre live)
- Soft delete ricevuta `annullata` (legacy DB only; API = hard delete)
- Colonne breakdown ricevute nell’export Excel corrispettivi
- Assumere che `data_incasso` guidi i corrispettivi

---

## 8. Riferimenti rapidi API

```typescript
// Corrispettivi
GET  /api/v1/corrispettivi/riepilogo?year=&month=&id_platform=&id_store=&delivery_country_iso=&day=
GET  /api/v1/corrispettivi/?year=&month=&...   // summary + sales_breakdown
POST /api/v1/corrispettivi/export              // body: { year, month, filters? }

// Ricevute
GET    /api/v1/ricevute
POST   /api/v1/ricevute
GET    /api/v1/ricevute/{id}
PUT    /api/v1/ricevute/{id}
DELETE /api/v1/ricevute/{id}                   // 204
GET    /api/v1/ricevute/{id}/pdf

// Resi
POST   /api/v1/orders/{id_order}/returns
GET    /api/v1/orders/returns/
DELETE /api/v1/orders/returns/{id_fiscal_document}
```

Permessi: vedi § Obiettivo. Swagger BE per shape esatte aggiornate.

---

**Fine prompt — incollare da qui sotto in chat FE**

---

Sei il team FE del gestionale Angular e-commerce. Implementa/aggiorna le schermate **Corrispettivi**, **Ricevute estero** e i flussi **Resi** collegati, seguendo le specifiche sopra e i documenti BE `docs/CORRISPETTIVI.md` + `docs/FE_HANDOFF_RICEVUTE.md`.

Priorità:
1. Refactor UI corrispettivi (`/riepilogo` 4 voci IVA + audit `sales_breakdown`)
2. Allineamento ricevute (DELETE 204, datetime emissione, warning `is_modifiable`, impatto corrispettivi)
3. UX resi con refresh/navigazione verso corrispettivi

Usa NgRx dove già presente per fiscal_documents. Mantieni coerenza visiva con fatture/DDT esistenti. Documenta in README FE le schermate toccate e i permessi RBAC.
