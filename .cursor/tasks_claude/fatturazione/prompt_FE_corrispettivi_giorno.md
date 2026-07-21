# Prompt sessione FE — Corrispettivo giornaliero (singolo giorno)

Copia tutto il contenuto **sotto la riga `---`** e incollalo in una nuova chat Cursor sul **repository del gestionale Angular**.

**Prerequisiti BE (obbligatori su dev/staging):**
- API BE aggiornata con endpoint corrispettivo giornaliero (2026-07-21)
- Swagger: `http://<BE_HOST>/docs` → tag **Corrispettivi**

**Documentazione BE (fonte di verità):**
- `docs/CORRISPETTIVI.md` (repo BE) — §2 Organizzazione endpoint, §4.4 Corrispettivo singolo giorno
- Prompt corrispettivi base (se non già implementato): `.cursor/tasks_claude/fatturazione/prompt_FE_corrispettivi_ricevute_resi.md`

**Permesso RBAC:** `fiscal_documents:read` (identico alla schermata corrispettivi mensile)

---

## Obiettivo sessione FE

Implementare in UI la possibilità di **generare e consultare il corrispettivo di un singolo giorno** del mese selezionato, oltre al flusso mensile già esistente.

Casi d’uso amministrativi tipici:
- Chiusura/rettifica di un giorno specifico
- Export Excel del solo giorno 15/07 senza scaricare l’intero mese
- Verifica rapida aliquote IVA di una data (es. dopo emissione ricevuta differita)

I corrispettivi restano **report live**: nessuno snapshot. Ogni GET ricalcola da ordini, resi e ricevute.

---

## 1. Cosa cambia rispetto al flusso mensile

| Aspetto | Flusso **mese** (esistente) | Flusso **giorno** (nuovo) |
|---------|----------------------------|---------------------------|
| Tabella riepilogo | Tutti i giorni 01..ultimo | **Una sola riga** (giorno selezionato) |
| Summary KPI | `days[]` con N giorni | `days[]` con **1 elemento** |
| Export | `POST /export` → `Registri.zip` | `POST /giorno/export` → `Registro_YYYY-MM-DD.zip` |
| Filtro `day` | Opzionale su GET mensili | **Obbligatorio** su endpoint `/giorno/*` |
| Response | `day: null` | `day: 15` (valorizzato) |

**Regola UI:** quando l’utente seleziona un giorno e clicca «Genera», usare preferibilmente gli endpoint dedicati `/giorno/*` (contratto più chiaro). In alternativa equivalente: GET mensili con query `?day=15`.

---

## 2. Controlli UI da aggiungere / estendere

### 2.1 Selettore giorno

Aggiungere un controllo **Giorno** accanto ad Anno e Mese:

| Controllo | Tipo suggerito | Comportamento |
|-----------|----------------|---------------|
| Giorno | `mat-select` o datepicker parziale (solo day) | Valori 1..`lastDayOfMonth`; disabilitato finché mese non selezionato |
| «Tutto il mese» | checkbox o opzione «—» nel dropdown | Se attivo → flusso mensile (nessun `day`) |
| Validazione locale | prima della chiamata API | Non inviare `day=31` su febbraio; mostrare errore inline |

**Suggerimento UX:** default «Tutto il mese». Quando l’utente sceglie un giorno, aggiornare label pulsanti:
- «Genera mese» → «Genera giorno 15/07/2026»
- «Esporta» → «Esporta giorno 15/07/2026»

### 2.2 Due modalità di generazione

```
┌─────────────────────────────────────────────────────────┐
│  Filtri: Anno | Mese | [Giorno opzionale] | Store...   │
└───────────────────────────┬─────────────────────────────┘
                            │
         ┌──────────────────┴──────────────────┐
         │ Giorno NON selezionato               │ Giorno selezionato (es. 15)
         ▼                                      ▼
  GET /riepilogo?year&month              GET /giorno/riepilogo?year&month&day=15
  GET /?year&month (opzionale)          GET /giorno?year&month&day=15 (opzionale KPI)
  POST /export { year, month }          POST /giorno/export { year, month, day, filters? }
```

### 2.3 Tabella riepilogo in modalità giorno

- Renderizzare **una riga** da `response.rows[0]` (non iterare 01..31)
- Footer totali: usare `month_totals` (per il giorno filtrato coincide col totale del giorno)
- Mostrare badge/header: «Corrispettivo del 15/07/2026»
- Se tutti zeri → messaggio informativo «Nessun movimento in questa data» (non nascondere la riga)

### 2.4 Pannello KPI / audit ricevute (opzionale)

Se già presente il drawer summary:
- In modalità giorno chiamare `GET /giorno` invece di `GET /`
- Mostrare `days[0].sales_breakdown` se presente (ricevute differite)
- Help testo invariato: imputazione su `data_emissione`, non su `data_incasso`

---

## 3. API — endpoint da integrare

Base: `/api/v1/corrispettivi`  
Header: `Authorization: Bearer <token>`

### 3.1 Consultazione giorno

```http
GET /api/v1/corrispettivi/giorno/riepilogo?year=2026&month=7&day=15&id_store=1
GET /api/v1/corrispettivi/giorno?year=2026&month=7&day=15
```

Query params opzionali (identici al mensile): `id_platform`, `id_store`, `delivery_country_iso`.

**Response riepilogo** — stesso schema mensile + campo `day`:

```typescript
interface CorrispettivoRiepilogoResponse {
  year: number;
  month: number;
  day: number | null;        // sempre valorizzato su /giorno/riepilogo
  calculation_mode: 'order_document_date';
  timezone: 'Europe/Rome';
  delivery_country_iso: string | null;
  columns: CorrispettivoTaxColumn[];
  rows: CorrispettivoRiepilogoRow[];  // length === 1
  month_totals: CorrispettivoRiepilogoTotals;
}
```

**Response summary** — stesso schema mensile + `day`; `days.length === 1`.

### 3.2 Export giorno

```http
POST /api/v1/corrispettivi/giorno/export
Content-Type: application/json

{
  "year": 2026,
  "month": 7,
  "day": 15,
  "filters": {
    "id_platform": null,
    "id_store": 1,
    "delivery_country_iso": null
  }
}
```

| Campo | Obbligatorio | Note |
|-------|--------------|------|
| `year`, `month`, `day` | Sì | `day` validato sul calendario (422 se 30/02) |
| `filters` | No | Solo `id_platform`, `id_store`, `delivery_country_iso` — **non** mettere `day` dentro `filters` |

**Response 200:**
- `Content-Type: application/zip`
- `Content-Disposition: attachment; filename="Registro_2026-07-15.zip"`
- Contenuto: `registro.xlsx` + `registro_{ISO}.xlsx` per paesi con movimenti **in quel giorno**

**Alternativa equivalente** (se preferite un solo metodo export):
```json
POST /api/v1/corrispettivi/export
{ "year": 2026, "month": 7, "filters": { "day": 15, "id_store": 1 } }
```
→ stesso ZIP, stesso filename `Registro_2026-07-15.zip`.

### 3.3 Errori

| HTTP | Caso | Azione FE |
|------|------|-----------|
| `401` | Token assente/scaduto | Redirect login / refresh token |
| `403` | Permesso `fiscal_documents:read` mancante | Messaggio permessi |
| `422` | Giorno non valido per il mese (es. 31/04) | Errore validazione sul selettore giorno |
| `500` | Errore aggregazione | Toast generico + retry |

Esempio body 422:
```json
{ "detail": "Giorno 30 non valido per 02/2026 (massimo 28)" }
```

---

## 4. Modelli TypeScript

Estendere `src/app/features/corrispettivi/models/corrispettivo.models.ts`:

```typescript
export interface CorrispettivoRiepilogoResponse {
  year: number;
  month: number;
  day?: number | null;
  // ... resto invariato
}

export interface CorrispettivoListResponse {
  year: number;
  month: number;
  day?: number | null;
  // ... resto invariato
}

export interface CorrispettivoDayExportRequest {
  year: number;
  month: number;
  day: number;
  filters?: Omit<CorrispettivoFilters, 'day'>;
}

export type CorrispettivoScope = 'month' | 'day';

export interface CorrispettivoPeriodSelection {
  year: number;
  month: number;
  day?: number | null;
  scope: CorrispettivoScope;
}
```

---

## 5. Servizio HTTP

Estendere `corrispettivo-api.service.ts`:

```typescript
loadRiepilogoGiorno(params: CorrispettivoQueryParams & { day: number }) {
  return this.http.get<CorrispettivoRiepilogoResponse>(
    `${this.baseUrl}/giorno/riepilogo`,
    { params: this.toHttpParams(params) }
  );
}

loadSummaryGiorno(params: CorrispettivoQueryParams & { day: number }) {
  return this.http.get<CorrispettivoListResponse>(
    `${this.baseUrl}/giorno`,
    { params: this.toHttpParams(params) }
  );
}

exportGiorno(body: CorrispettivoDayExportRequest): Observable<Blob> {
  return this.http.post(`${this.baseUrl}/giorno/export`, body, {
    responseType: 'blob',
    observe: 'response',
  }).pipe(map(res => {
    // opzionale: estrarre filename da Content-Disposition
    return res.body!;
  }));
}

/** Router interno: sceglie endpoint in base a scope */
loadRiepilogo(selection: CorrispettivoPeriodSelection) {
  if (selection.scope === 'day' && selection.day) {
    return this.loadRiepilogoGiorno({ ...selection, day: selection.day });
  }
  return this.loadRiepilogoMese(selection);
}
```

**Download blob export giorno:**
```typescript
exportGiorno(selection: CorrispettivoPeriodSelection, filters: CorrispettivoFilters) {
  const filename = `Registro_${selection.year}-${pad(selection.month)}-${pad(selection.day!)}.zip`;
  this.corrispettivoApi.exportGiorno({
    year: selection.year,
    month: selection.month,
    day: selection.day!,
    filters,
  }).subscribe(blob => this.fileDownload.save(blob, filename));
}
```

---

## 6. NgRx (se già in uso)

### State

```typescript
interface CorrispettiviState {
  selection: CorrispettivoPeriodSelection;  // scope: 'month' | 'day'
  riepilogo: CorrispettivoRiepilogoResponse | null;
  summary: CorrispettivoListResponse | null;
  loading: boolean;
  exporting: boolean;
  error: string | null;
}
```

### Actions suggerite

```typescript
setPeriod({ year, month, day?, scope })
loadRiepilogo()           // effect: branch month vs day
loadSummary()             // opzionale, stesso branch
exportRegistri()          // POST /export o /giorno/export in base a scope
exportRegistriSuccess()
exportRegistriFailure({ error })
```

### Effect (pseudo)

```typescript
loadRiepilogo$ = createEffect(() =>
  this.actions$.pipe(
    ofType(loadRiepilogo),
    withLatestFrom(this.store.select(selectSelection), selectFilters),
    switchMap(([_, selection, filters]) =>
      selection.scope === 'day' && selection.day
        ? this.api.loadRiepilogoGiorno({ ...selection, ...filters, day: selection.day })
        : this.api.loadRiepilogoMese({ ...selection, ...filters })
    ),
    map(riepilogo => loadRiepilogoSuccess({ riepilogo })),
    catchError(err => of(loadRiepilogoFailure({ error: err.message })))
  )
);
```

---

## 7. Flusso UI consigliato

```
1. Utente seleziona Anno + Mese
2. (Opzionale) seleziona Giorno → scope = 'day'
3. Click «Genera»
   → dispatch loadRiepilogo()
   → GET /giorno/riepilogo oppure GET /riepilogo
4. Render tabella (1 riga se giorno, N righe se mese)
5. Click «Esporta»
   → POST /giorno/export oppure POST /export
   → download Registro_YYYY-MM-DD.zip o Registri.zip
```

**Messaggistica utente** (banner o help):
> I corrispettivi sono calcolati in tempo reale. Fatturare un ordine, emettere/eliminare una ricevuta o registrare un reso modifica i totali anche dei giorni già consultati.

---

## 8. Checklist implementazione

### UI / componenti
- [ ] Selettore giorno (1..lastDayOfMonth) con opzione «Tutto il mese»
- [ ] Validazione locale giorno/mese (es. 31 febbraio bloccato prima della chiamata)
- [ ] Label pulsanti dinamiche (Genera/Esporta mese vs giorno)
- [ ] Header/badge data quando scope = day
- [ ] Tabella: 1 riga in modalità giorno; footer totali da `month_totals`
- [ ] Stato empty «Nessun movimento» se riga a zero

### API / servizi
- [ ] Metodi `loadRiepilogoGiorno`, `loadSummaryGiorno`, `exportGiorno`
- [ ] Branch month/day negli effect o nel service facade
- [ ] Download blob con filename `Registro_YYYY-MM-DD.zip`
- [ ] Gestione 422 con messaggio sul selettore giorno

### Modelli / store
- [ ] Campo `day?: number | null` nei modelli response
- [ ] `CorrispettivoDayExportRequest` e `CorrispettivoScope`
- [ ] Selector `selectIsDayScope`, `selectPeriodLabel`

### QA manuale

| # | Scenario | Atteso |
|---|----------|--------|
| 1 | Genera mese intero (no day) | Tabella con tutti i giorni; export `Registri.zip` |
| 2 | Genera giorno 15 con ordini | 1 riga con totali > 0; `response.day === 15` |
| 3 | Genera giorno senza movimenti | 1 riga tutti zeri; messaggio informativo |
| 4 | Export giorno 15 | ZIP `Registro_2026-07-15.zip`; Excel footer «Totale 15/07/2026» |
| 5 | Giorno 30 su febbraio 2026 | 422; errore UI sul selettore |
| 6 | Cambio mese con giorno 31 selezionato | Reset giorno o clamp a lastDayOfMonth |
| 7 | Filtro store + giorno | Stessi filtri su GET e POST export |
| 8 | Ricevuta differita nel giorno emissione | KPI mostra `sales_breakdown.ricevute_imputazione` |

---

## 9. Fuori scope / non fare

- Non persistere snapshot corrispettivi lato FE (sempre live)
- Non usare `data_incasso` ricevuta per logiche corrispettivi
- Non assumere che prodotti e spedizione condividano la stessa aliquota nella stessa colonna
- Non filtrare lato FE i giorni a zero in modalità **mese** (mostrare tutti 01..ultimo)
- In modalità **giorno**, non chiamare il mensile e filtrare client-side: usare `/giorno/*`

---

## 10. Riferimento rapido endpoint

```
# Mensile (esistente)
GET  /api/v1/corrispettivi/riepilogo?year=&month=&id_platform=&id_store=&delivery_country_iso=&day=
GET  /api/v1/corrispettivi/?year=&month=&...
POST /api/v1/corrispettivi/export

# Giornaliero (nuovo — preferito quando day selezionato)
GET  /api/v1/corrispettivi/giorno/riepilogo?year=&month=&day=
GET  /api/v1/corrispettivi/giorno?year=&month=&day=
POST /api/v1/corrispettivi/giorno/export
```

---

## Prompt operativo (incolla in chat FE)

Sei il team FE del gestionale Angular e-commerce. Implementa la **generazione corrispettivo giornaliero** sulla schermata corrispettivi esistente, seguendo le specifiche sopra e `docs/CORRISPETTIVI.md` §4.4 (repo BE).

Priorità:
1. Selettore giorno + branch API month/day
2. Tabella riepilogo a singola riga + export `Registro_YYYY-MM-DD.zip`
3. Validazione calendario e gestione errori 422
4. (Opzionale) KPI/audit `sales_breakdown` su `GET /giorno`

Non refactorare ricevute/resi in questa sessione salvo impatti diretti sui totali giornalieri.
