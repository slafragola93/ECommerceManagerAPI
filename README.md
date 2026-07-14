# ECommerceManagerAPI

API REST per ordini, resi, documenti fiscali, spedizioni e sincronizzazione e-commerce (PrestaShop).

---

## Requisiti

- **Python 3.10+**
- **MySQL**
- (Opzionale) Redis per cache

---

## Installazione dipendenze

```bash
# Dalla root del progetto
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

# Installa le dipendenze
pip install -r requirements.txt
```

---

## Configurazione

Copia il file ambiente e imposta le variabili (database e JWT):

```bash
# Windows
copy env.example .env

# Linux / macOS
cp env.example .env
```

Modifica `.env` con almeno:

- `DATABASE_MAIN_USER`, `DATABASE_MAIN_PASSWORD`, `DATABASE_MAIN_ADDRESS`, `DATABASE_MAIN_PORT`, `DATABASE_MAIN_NAME`
- `SECRET_KEY` (per JWT)
- `FASTLDV_API_KEY` (per app magazzino FastLDV; vedi sotto)

Applica le migrazioni al database:

```bash
alembic upgrade head

# Tabella ricevute (feature Ricevute estero — obbligatoria prima dei GET /api/v1/ricevute):
python scripts/migrations/create_ricevute_table.py
# Data/ora emissione (DATE → DATETIME, se tabella già esistente):
python scripts/migrations/alter_ricevute_data_emissione_datetime.py
```

> **Nota:** finché `ricevute` non esiste, le API ricevute rispondono **500**. Eseguire lo script su ogni ambiente (dev/staging/prod) dopo il deploy del codice BE.

---

## Esecuzione script

**Setup iniziale** (Order State, Shipping State, App Configuration, Platform, Store, Role, utente admin, CompanyFiscalInfo, colonna `orders.vies_status`, seed IVA UE):

```bash
python scripts/setup_initial.py
```

Lo script è **idempotente**: aggiunge `vies_status` su `orders` se assente e crea/aggiorna i `Tax` default per i 27 paesi UE (`Tax.id_country` + `is_default=1`). Richiede che la tabella `countries` contenga i codici ISO corrispondenti (es. da sync PrestaShop).

Altri script utili:

```bash
# Solo configurazioni app
python scripts/init_app_configurations.py

# Warm cache (se usi cache)
python scripts/warm_cache.py
```

---

## Avvio applicazione

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

- **API**: http://localhost:8000  
- **Swagger**: http://localhost:8000/docs  
- **Health**: http://localhost:8000/api/v1/health (se esposto)

---

## API — Default IVA per paese (VIES Fase 1)

Prefisso esistente `/api/v1/taxes`. Permessi RBAC: modulo `settings`, azioni `read` / `update`.

| Metodo | Path | Descrizione |
|--------|------|-------------|
| GET | `/api/v1/taxes/country-defaults` | Lista `Tax` con `is_default=1` per paese |
| GET | `/api/v1/taxes/country-defaults/{iso_code}` | Default per paese (es. `IT`) |
| PUT | `/api/v1/taxes/{id_tax}/set-country-default` | Imposta unico default per `id_country` del Tax |

Il payload `/api/v1/init/` espone già `taxes[]` con `id_country` e `is_default` (nessuna chiave aggiuntiva).

---

## API — VIES ordini (BE-VIES-2, Fase 2/4)

Prefisso `/api/v1/orders`. Permessi RBAC: `orders.read` (filtro lista), `orders.update` (esenzione).

| Metodo | Path | Descrizione |
|--------|------|-------------|
| GET | `/api/v1/orders/?vies_status=eligible\|not_eligible\|null` | Filtro snapshot VIES (`null` = solo `vies_status` IS NULL; assenza param = tutti) |
| PATCH | `/api/v1/orders/{id}/vies-status` | **Nuovo (03/07):** aggiornamento bidirezionale `{ "status": "eligible" \| "not_eligible" }`. `eligible` = esenzione completa (righe + spedizione + totali). `not_eligible` = label + IVA spedizione; righe/totali da FE |
| PATCH | `/api/v1/orders/{id}/apply-vies-exemption` | Legacy — equivalente a `vies-status` con `eligible` |
| POST | `/api/v1/orders/bulk-apply-vies-exemption` | Stessa logica su `{ "order_ids": [1,2,...] }` in transazione atomica |
| GET | `/api/v1/orders/{id}/pdf` | PDF stampa singolo ordine (layout elettronew: logo, barcode, intestazione/consegna, righe, totali) |

Guida FE: [docs/FE_VIES_APPLY_EXEMPTION_BUTTON.md](docs/FE_VIES_APPLY_EXEMPTION_BUTTON.md) — prompt chat FE: [.cursor/tasks_claude/prompt_FE_vies_apply_exemption.md](.cursor/tasks_claude/prompt_FE_vies_apply_exemption.md).

Ricalcolo BE: `calculate_price_without_tax` (righe) + `OrderService.recalculate_totals_for_order` (totali ordine).

Eventi: `ORDER_VIES_STATUS_CHANGED` (PATCH vies-status), `ORDER_VIES_EXEMPTION_APPLIED` (solo su `eligible`).

---

## API — Ricevute estero (BE-1 + BE-2.2)

Documenti fiscali interni (no SDI) per clienti esteri privati senza P.IVA. Dati ordine/cliente/righe sempre **live** (nessuna tabella righe o snapshot).

Prefisso `/api/v1/ricevute`. Permesso RBAC: `fiscal_documents:read` (come corrispettivi).

| Metodo | Path | Descrizione |
|--------|------|-------------|
| GET | `/api/v1/ricevute` | Lista paginata con filtri `id_order`, `id_customer`, `stato`, `data_emissione_from`, `data_emissione_to` |
| GET | `/api/v1/ricevute/{id_ricevuta}` | Dettaglio con ordine, cliente, indirizzi e `order_details` live |
| POST | `/api/v1/ricevute` | Crea ricevuta da ordine (`id_order`, `data_emissione` opzionale datetime); genera PDF |
| PUT | `/api/v1/ricevute/{id_ricevuta}` | Aggiorna `data_emissione` (data + ora); rigenera PDF |
| DELETE | `/api/v1/ricevute/{id_ricevuta}` | Cancellazione definitiva (**204 No Content**); rimuove record e PDF |
| GET | `/api/v1/ricevute/{id_ricevuta}/pdf` | Download PDF (rigenera se assente); `?regenerate=1` forza nuovo template |
| POST | `/api/v1/ricevute/{id_ricevuta}/pdf` | Rigenera PDF (sovrascrive) |
| GET | `/api/v1/ricevute/{id_ricevuta}/export?fmt=csv\|xlsx` | Export singola ricevuta con `order_details` |
| GET | `/api/v1/ricevute/export?fmt=csv\|xlsx&...` | Export massivo (stessi filtri lista, max 5000 righe) |

Permessi write: `fiscal_documents:create|update|delete`.

**Migration:** modello `src/models/ricevuta.py`, script `scripts/migrations/create_ricevute_table.py` e `alter_ricevute_data_emissione_datetime.py`. Numerazione annuale `(numero, anno)` con `UNIQUE` e `get_next_numero()` (`SELECT FOR UPDATE`). Lista ordinata per `data_emissione` DESC (con ora), poi `numero` DESC.

**PDF ricevuta:** layout elettronew dedicato (`src/services/pdf/ricevuta_pdf_layout.py`) — logo + anagrafica, titolo `RICEVUTA n° {numero}/{anno} la {gg/mm/aaaa hh:mm}`, colonne En-tête / indirizzo consegna (label FR se cliente estero), tabella righe (Code, Prix/TVA/…), riferimento ordine, totali a destra (merce, spedizione, IVA, totale — senza voce spese incasso). Non include note ordine (solo uso interno app). Non riusa più il layout fattura SDI.

**PDF fattura/nota di credito:** `date_add` mostrato con data e ora (`gg/mm/aaaa hh:mm`, Europe/Rome). XML FatturaPA resta con sola data (requisito SDI).

Prossimi step: BE-3 impatto corrispettivi, BE-2.5 export, BE-2.6 email.

**Handoff FE:** [docs/FE_HANDOFF_RICEVUTE.md](docs/FE_HANDOFF_RICEVUTE.md) — prompt implementazione: [prompt_FE_ricevute.md](.cursor/tasks_claude/fatturazione/prompt_FE_ricevute.md) — **prompt test FE:** [prompt_FE_ricevute_TEST.md](.cursor/tasks_claude/fatturazione/prompt_FE_ricevute_TEST.md)

## Ultime modifiche (2026-07-14) — Corrispettivi: resi spedizione in riepilogo

- `GET /api/v1/corrispettivi/riepilogo` → `rows[].shipping` allineato alle celle aliquota: `sales_net`, `returns_net`, **`net`** (importo reso in rosso lato FE).
- Resi con `includes_shipping=true` e totali netti assenti/zerati: fallback su `shipments.price_tax_excl` dell'ordine.
- Test: `tests/unit/repository/test_corrispettivo_return_shipping.py`. Doc: `docs/CORRISPETTIVI.md`.

## Ultime modifiche (2026-07-08) — BE-2.5 Export CSV/Excel

- `GET /api/v1/ricevute/{id}/export?fmt=csv|xlsx` — dettaglio + righe prodotto.
- `GET /api/v1/ricevute/export?fmt=...` — export massivo filtrato (max 5000).
- Service: `src/services/export/ricevuta_export_service.py`.

## Ultime modifiche (2026-07-10) — Ricevute: nessun blocco BE su Spedizione Confermata

- `POST`, `PUT` e `DELETE` consentiti anche con `id_order_state == 4` (ordine evaso).
- `is_modifiable` resta indicatore FE per warning opzionali.

## Ultime modifiche (2026-07-09) — Corrispettivi: regola ricevute per date ordine/emissione

- Confronto **`Order.date_add` vs `data_emissione`** (non più `data_incasso`).
- Stesso giorno ordine/emissione → importo resta in **vendite base** del giorno ordine.
- Giorni diversi → decurtazione su **date ordine**, imputazione su **data emissione ricevuta**.

## Ultime modifiche (2026-07-09) — DELETE ricevuta: cancellazione definitiva

- `DELETE /api/v1/ricevute/{id}` restituisce **204 No Content** (non più soft delete `annullata`).
- Rimuove record DB e file PDF in `media/ricevute/`.
- Dopo la cancellazione l'ordine può ricevere una nuova ricevuta; i corrispettivi tornano al flusso vendite standard (come per annullo legacy).

## Ultime modifiche (2026-07-09) — PDF ricevuta: rimossa voce Spese incasso

- Nel blocco totali del PDF non compare più la riga **Spese incasso - {metodo pagamento}** (era sempre € 0,00).
- Rigenerare PDF esistenti con `GET /api/v1/ricevute/{id}/pdf?regenerate=1`.

## Ultime modifiche (2026-07-09) — API ricevuta: spedizione in totali e righe

- `order_details[]` include riga spedizione (`is_shipping: true`) quando presente.
- `order.shipping_total_price_with_tax` / `shipping_total_price_net` su dettaglio.
- Logica condivisa PDF + API: `src/services/ricevute/order_lines.py`.
- Export CSV/XLSX: colonna `is_shipping`.

## Ultime modifiche (2026-07-09) — PDF ricevuta: spedizione in tabella e totali

- Caricamento spedizione via `id_shipping` (come stampa ordine), non solo relationship `shipments`.
- Riga **Spedizione/Livraison** in tabella prodotti + riga totali con importo IVA inclusa.
- Fallback: se record spedizione assente, deriva da `total_price_with_tax - products_total_price_with_tax`.

## Ultime modifiche (2026-07-08) — Template PDF ricevuta elettronew

- Nuovo layout B/N allineato al documento legacy (non più layout fattura con box VENDITORE/CLIENTE).
- File: `src/services/pdf/ricevuta_pdf_layout.py` + refactor `ricevuta_pdf_service.py`.
- Label localizzate FR (`En-tête`, `Prix`, `TVA`, `Frais de collecte`, …) in base a `country.iso_code` del cliente.
- Colonna IVA: preferisce `Tax.code` (es. `20FR`), altrimenti `{percentuale}{iso}`.
- Test: `tests/unit/services/pdf/test_ricevuta_pdf_service.py`.

## Ultime modifiche (2026-07-08) — BE-3.3 Ricevute + resi

- Test integrazione: delete reso su ordine con/senza ricevuta; annullo ricevuta post-delete.
- Fix normalizzazione date movimenti corrispettivi (chiavi `date` coerenti su SQLite/MySQL).

## Ultime modifiche (2026-07-08) — BE-3.2 Corrispettivi UNION ALL

- `fetch_sales_gross_breakdown_by_day`: base / decurtazione / imputazione in un'unica query.
- `GET /api/v1/corrispettivi` → `days[].sales_breakdown` per audit ricevute.

## Ultime modifiche (2026-07-08) — BE-3.1 Corrispettivi + ricevute

- Ordini con ricevuta emessa esclusi da vendite su `date_add`.
- Decurtazione su `data_incasso`, imputazione su `data_emissione` (imponibile per aliquota + lordo in summary).
- Test: `tests/unit/repository/test_corrispettivo_ricevute.py`. Doc: `docs/CORRISPETTIVI.md`.

## Ultime modifiche (2026-07-08) — Naming allineato app

- Dettaglio ricevuta: `righe` → **`order_details`** (come ordini/resi); tipo `RicevutaOrderDetailEmbedSchema`.

## Ultime modifiche (2026-07-08) — Contratto API ricevute snellito

- Dettaglio: rimossi `id_order`/`id_customer`/`pdf_hash` duplicati in root; `customer`/`order`/`address_delivery`/`address_invoice` embed leggeri.
- `is_modifiable` solo a livello ricevuta; indirizzi senza customer annidato.

## Ultime modifiche (2026-07-08) — Fix PDF ricevuta (Decimal MySQL)

- Fix generazione PDF: cast esplicito `Decimal` → `float` in `FiscalDocumentPDFService` (spedizione/totali da MySQL).
- Se il PDF fallisce in `POST /ricevute`, il record viene rollback (delete) e risposta **400** invece di 500.

## Ultime modifiche (2026-07-08) — Ricevute BE-2.1 / BE-2.3 / BE-2.4

- `POST /api/v1/ricevute` — creazione da ordine, numerazione annuale, `data_incasso` da `payment_date`.
- PDF automatico alla creazione; `GET/POST .../pdf` download/rigenerazione; file in `media/ricevute/{anno}/`.
- `POST` / `PUT` / `DELETE` ricevute: nessun blocco BE su Spedizione Confermata; `is_modifiable` per warning FE.
- Helper condiviso `resolve_order_payment_date` per allineamento corrispettivi (BE-3).

## Ultime modifiche (2026-07-08) — Ricevute BE-1 + BE-2.2

- Tabella `ricevute` (modello SQLAlchemy, migration script).
- Endpoint GET lista/dettaglio con join live ordine/cliente/righe.
- Flag `is_modifiable` derivato da `id_order_state != 4` — indicatore FE (non blocca POST/PUT/DELETE).
- Registrazione DI (`IRicevutaRepository`, `IRicevutaService`) e router in `main.py`.

## Ultime modifiche (2026-07-03) — BE-1 bridge persist-if-complete

**Scope:** il BE persiste i prezzi inviati dal FE quando il payload riga è completo; altrimenti mantiene il calcolo legacy.

- Helper: `src/services/core/price_persistence.py` (`resolve_price_fields`, `has_complete_price_update_payload`).
- Integrato in `order_service.add/update_order_detail` e `order_detail_service`.
- Payload completo PUT riga: `id_tax` + `unit_price_net` + `unit_price_with_tax` + `total_price_net` + `total_price_with_tax`.
- `OrderDetailCreateSchema`: aggiunti `unit_price_net` / `total_price_net` opzionali.
- **Test:** `tests/unit/services/test_price_persistence.py`, `tests/unit/services/test_order_detail_price_bridge.py`.

## Ultime modifiche (2026-07-03) — PATCH vies-status bidirezionale

**Scope:** endpoint `PATCH /api/v1/orders/{id}/vies-status` per CTA FE Applica VIES / Update stato VIES.

- **`eligible`:** riusa logica esenzione (righe 0% keep_gross, spedizione 0%, ricalcolo totali).
- **`not_eligible`:** aggiorna `vies_status` e riattiva IVA sulla spedizione (`id_tax` standard + `price_tax_incl` da imponibile); **non** modifica righe né totali ordine (valori da operatore via PUT).
- Helper: `reactivate_shipping_vat_for_order` in `src/vies/exemption_calculation.py`.
- **Test:** `tests/unit/vies/test_reactivate_shipping_vat.py`, `tests/integration/api/v1/test_order_patch_vies_status.py`.

## Ultime modifiche (2026-06-22) — VIES esenzione reale

**Scope:** apply-vies-exemption e creazione ordine con `vies_status=eligible` sottraggono l'IVA reale (righe + spedizione); sync PrestaShop invariato.

- **Prima:** lordo riga invariato, imponibile gonfiato a 0% IVA; spedizione non toccata.
- **Dopo:** lordo = netto al netto reale (es. 122 € @ 22% → 100 €); spedizione stessa logica; totali ordine diminuiscono.
- **Fallback aliquota** (se `id_tax` assente): default paese consegna → default globale → 0%.
- **Righe già a 0%:** nessuna sottrazione (importi invariati), solo normalizzazione `id_tax` VIES.
- **Sync PS** con `eligible` e IVA 0%: dati copiati fedelmente, nessuna sovrascrittura.

**Test:** `tests/unit/vies/test_vies_exemption_calculation.py`, `tests/unit/services/test_order_vies_exemption*.py`, `tests/unit/repository/test_order_create_vies_eligible_tax.py`, `tests/integration/api/v1/test_order_vies_exemption.py` (totali in response PATCH + persistenza GET).

**Delete tax:** `DELETE /api/v1/taxes/{id}` — se la tax è referenziata restituisce **422** con `error_code: TAX_IN_USE` e `details: { orders, documents, is_reverse_charge }` (BE-ALIQ-02).

---

## Ultime modifiche (2026-07-06) — Corrispettivi: regole vendite vs resi

**Vendite:** solo ordini **non fatturati** e **pagati** (`is_payed = true`).

**Resi:** ordine **pagato** e (**non fatturato** oppure con **nota di credito**). Un reso su ordine fatturato senza NC resta escluso; con NC collegata entra nei corrispettivi.

Test: `tests/unit/repository/test_corrispettivo_repository.py`

---

- **Resi** eliminabili in qualsiasi stato (`DELETE /api/v1/orders/returns/{id}`); fatture/NC solo se `pending`.
- Risposta JSON strutturata al delete reso/dettaglio; errori 404/400 non più mascherati in 400 generico.
- Delete dettaglio consentito solo su documenti `return`.
- Test: `tests/unit/repository/test_fiscal_document_delete_return.py`.

---

## Ultime modifiche (2026-07-13) — Fix `data_emissione` date-only in PDF ricevuta

**Bugfix produzione:** `POST /api/v1/ricevute/` poteva fallire con `400` e messaggio `'datetime.date' object has no attribute 'tzinfo'` durante la generazione PDF quando `data_emissione` arrivava come sola data (`YYYY-MM-DD`) o come oggetto `date` legacy.

**Fix:**
- Parsing API robusto in `RicevutaCreateSchema` / `RicevutaUpdateSchema`: accetta `YYYY-MM-DD` (→ `date`, ora corrente Europe/Rome in persistenza) e ISO datetime con/senza offset (`YYYY-MM-DDTHH:mm:ss[Z|offset]`).
- Utility `parse_emission_input`, `emission_to_rome`, `emission_for_pdf` in `src/services/ricevute/date_utils.py` — nessun accesso diretto a `.tzinfo` su `date`.
- PDF: normalizzazione timezone-aware Europe/Rome prima del render (`ricevuta_pdf_service.py`).

**Test:** `tests/unit/services/ricevute/test_date_utils.py`, `tests/unit/services/test_ricevuta_create.py`, `tests/unit/services/pdf/test_ricevuta_pdf_service.py`.

## Ultime modifiche (2026-07-13) — API ricevuta: indirizzi sempre delivery/invoice

- Dettaglio `GET /api/v1/ricevute/{id}`: rimosso campo `address`; sempre `address_delivery` e `address_invoice` (nullable).
- Se consegna = fatturazione, entrambi i campi contengono lo stesso oggetto (contratto stabile per il FE).

## Ultime modifiche (2026-07-10) — Data/ora emissione ricevute e fatture

- `ricevute.data_emissione` è **DATETIME** (migration `alter_ricevute_data_emissione_datetime.py`); API e export espongono ISO 8601 con ora.
- Default creazione: adesso (Europe/Rome). Accetta anche solo la data (ora corrente sul giorno indicato).
- Ordinamento lista e PDF: `gg/mm/aaaa hh:mm` per allineare i progressivi emessi in momenti diversi dello stesso giorno.
- PDF fattura/nota di credito: stesso formato ora su `date_add`.
- Corrispettivi: aggregazione per **giorno** emissione invariata (`Europe/Rome`).

Test: `tests/unit/services/ricevute/test_date_utils.py`, suite ricevute/corrispettivi esistente.

## Ultime modifiche (2026-07-14) — Export corrispettivi: riepilogo generico con aliquote

Il file consolidato `registro.xlsx` nel ZIP `Registri.zip` include ora la **suddivisione per aliquota IVA** (vendite, resi, netto per ogni aliquota), allineata a `GET /api/v1/corrispettivi/riepilogo`. Restano anche i totali di riga e la colonna spedizione.

I file per paese (`registro_{ISO}.xlsx`) mantengono il formato compatto a 5 colonne: **Data**, **Tot resi**, **Totale netto**, **Netto prodotti**, **Netto spedizione**.

Test: `tests/unit/services/export/test_corrispettivi_excel_service.py`.

## Ultime modifiche (2026-07-13) — Export corrispettivi: fix split per paese consegna

**Bugfix:** i file `registro_IT.xlsx`, `registro_FR.xlsx`, ecc. nel ZIP `Registri.zip` contenevano gli stessi dati del consolidato `registro.xlsx` perché il filtro `delivery_country_iso` non era applicato correttamente alle query di export (mancava il legame con l'indirizzo di consegna).

**Fix:** `_apply_order_filters` in `CorrispettivoRepository` usa ora una subquery `EXISTS` sull'indirizzo di consegna (`orders.id_address_delivery` → `countries.iso_code`). Ogni `registro_{ISO}.xlsx` include solo i movimenti con consegna in quel paese.

**Nota:** `registro.xlsx` (consolidato) = somma dei registri per paese. Se un paese (es. IT) ha totale mensile **0** — tipico con sole righe ricevuta decurtazione/imputazione che si compensano — il consolidato coincide con gli altri paesi che hanno il netto reale (es. FR). L'export ignora sempre `delivery_country_iso` nel body per il file consolidato, anche se il FE invia un filtro paese attivo.

Test: `tests/unit/repository/test_corrispettivo_repository.py` → `TestCorrispettivoDeliveryCountryFilter`.

## Ultime modifiche (2026-07-10) — PDF ricevuta: rimossa sezione NOTE

- Il PDF non include più `order.general_note` (note solo interne all'applicazione).
- Rigenerare con `GET /api/v1/ricevute/{id}/pdf?regenerate=1`.

## Ultime modifiche (2026-07-10) — Export Excel corrispettivi: solo netti e resi

I file `registro.xlsx` / `registro_{ISO}.xlsx` nel ZIP contengono **5 colonne**:

**Data**, **Tot resi**, **Totale netto**, **Netto prodotti**, **Netto spedizione** (importi **con IVA**).

Rimosse dal file Excel le colonne audit ricevute (`Vendite base`, `Ricevute decurtazione/imputazione`, `Totale vendite`). Il breakdown resta su `GET /api/v1/corrispettivi` → `days[].sales_breakdown`.

## Ultime modifiche (2026-07-09) — Export Excel corrispettivi: colonne ricevute

I file `registro.xlsx` / `registro_{ISO}.xlsx` nel ZIP includono il breakdown vendite BE-3.2:

**Data**, **Vendite base**, **Ricevute decurtazione**, **Ricevute imputazione**, **Totale vendite**, **Tot resi**, **Totale netto**, **Netto prodotti**, **Netto spedizione** (importi **con IVA**).

`Totale vendite` = somma delle tre colonne vendite; allineato a `GET /api/v1/corrispettivi` → `days[].sales_breakdown`.

Test: `tests/unit/services/export/test_corrispettivi_excel_service.py`.

---

## Ultime modifiche (2026-07-06) — Export Excel corrispettivi (layout precedente)

Layout storico a 6 colonne (senza breakdown ricevute) — sostituito dal formato sopra.

---

Report fiscale interno: vendite su ordini **non fatturati e pagati**; resi su ordini **pagati** non fatturati **o** fatturati con **nota di credito**.

**Endpoint** (`/api/v1/corrispettivi`, permesso `fiscal_documents:read`):

| Metodo | Path | Descrizione |
|---|---|---|
| GET | `/riepilogo?year=&month=` | Matrice giorni × aliquote (vendite nette, resi netti, netto); include `columns` con header aliquote |
| GET | `/?year=&month=` | Totali giornalieri con split prodotti/spedizione |
| POST | `/export` | ZIP `Registri.zip` (`registro.xlsx` + `registro_{ISO}.xlsx`) |

Filtri opzionali: `id_platform`, `id_store`, `delivery_country_iso`, `day`. Timezone aggregazione: `Europe/Rome`. Nessuna tabella DB dedicata (query live).

Documentazione: [`docs/CORRISPETTIVI.md`](docs/CORRISPETTIVI.md) (reference completa per FE: schemi TypeScript, NgRx, export blob)

Dipendenza aggiunta: `openpyxl` (export Excel).

Test: `tests/unit/services/corrispettivi/test_corrispettivi_aggregation.py`, `tests/unit/repository/test_corrispettivo_repository.py`, `tests/unit/services/export/test_corrispettivi_excel_service.py`

---

**Contratto API Tax (allineato a FatturaPA):**

| Campo | Contenuto | Uso XML FatturaPA |
|-------|-----------|-------------------|
| `electronic_code` | Codice natura breve (es. `N3.1`, `N3.2`) | tag `<Natura>` |
| `note` | Descrizione normativa (es. `Non imponibili - esportazioni`) | tag `<RiferimentoNormativo>` |

Il FE invia codice e descrizione su campi separati; non concatenare `CODICE - DESCRIZIONE` in `electronic_code`.

**DB:** colonna `taxes.electronic_code` portata a `VARCHAR(255)` (migration `20260622_0001`; head applicata).

**FatturaPA (step 1):**

- Fix bug riga 527: rimosso `{tax_electronic_code:.2f}` (crash su stringhe).
- `_prepare_order_data_from_fiscal_document` passa `tax_electronic_code` e `tax_note` da `Tax`.
- Helper `src/services/external/fatturapa_natura.py` — normalizza codice per `<Natura>`.
- Validator: accetta sottocodici `N3.1`–`N6.9`, rifiuta stringhe estese.

**Prossimi step (non in questo commit):** Natura per riga ordine, ramo VIES `N3.2`, tax per `id_tax` riga.

**Handoff FE:** [docs/FE_HANDOFF_TAX_ELECTRONIC_CODE.md](docs/FE_HANDOFF_TAX_ELECTRONIC_CODE.md)

**Handoff FE — Aliquote vs Default paese:** [docs/FE_HANDOFF_TAX_DEFAULT_VS_CATALOG.md](docs/FE_HANDOFF_TAX_DEFAULT_VS_CATALOG.md) — chiarimento `is_default` (non usare come toggle “attiva aliquota”); catalogo multiplo per paese vs un solo default automatico.

Test: `tests/unit/services/external/test_fatturapa_natura.py`, `tests/integration/api/v1/test_tax_electronic_code_length.py`.

---

## Ultime modifiche (2026-06-05) — BE-ALIQ-05 (Tax.percentage DECIMAL)

- Colonna `taxes.percentage`: `Integer` → `DECIMAL(5,2)` (modello SQLAlchemy + migration Alembic `20260605_0001`).
- Schema API: `percentage` come `Decimal` con risposta JSON numerica (`25.5`, `22`, …).
- Seed UE: Finlandia **25.5%** (prima troncata a 25).
- Setup idempotente: `setup_taxes_percentage_decimal_column()` in `scripts/setup_initial.py`.
- Deploy DB: `alembic upgrade head` **oppure** `python scripts/setup_initial.py` su MySQL.
- **Troubleshooting:** se PUT/POST invia `25.5` ma la response restituisce `26`, la colonna DB è ancora `INTEGER`. Verifica con `python scripts/check_tax_percentage_column.py` e applica la migration.
- Test: `tests/unit/schemas/test_tax_percentage_decimal.py`, `tests/integration/api/v1/test_tax_percentage_decimal.py`.

---

## Ultime modifiche (2026-06-05) — BE-ALIQ-04 (id_country int|null)

- `coerce_optional_int()` + validator Pydantic su `TaxSchema` / `TaxResponseSchema` — accetta input stringa (`"5"`) e serializza sempre `int | null`.
- Serializzazione centralizzata: `serialize_tax_response()` / `serialize_taxes_response()` usate da router Tax e `InitService._get_taxes`.
- Endpoint Tax (`GET/POST/PUT`) e `/api/v1/init/?include=static` restituiscono `id_country` tipizzato in modo coerente (niente stringhe difensive lato FE).
- Test: `tests/unit/schemas/test_tax_id_country.py`, `tests/integration/api/v1/test_tax_id_country.py`.

---

## Ultime modifiche (2026-06-05) — BE-ALIQ-03 (cache init su write Tax/Settings)

- Helper condiviso `invalidate_init_data_cache()` in `src/core/cache.py` — invalida `init_data:static` e `init_data:full`.
- Chiamato su **tutti** i write: `POST/PUT/DELETE /api/v1/taxes/`, `PUT .../set-country-default`, `PUT /api/v1/settings/` (reverse charge).
- Nessuna invalidazione se delete tax fallisce con `TAX_IN_USE`.
- Test: `tests/unit/core/test_init_cache_invalidation.py`, estensioni in `test_tax_service.py` e `test_settings_reverse_charge.py`.

---

## Ultime modifiche (2026-06-05) — BE-ALIQ-02 (delete Tax strutturato)

- Pre-check utilizzo tax prima della delete: righe ordine, dettagli documenti fiscali, `reverse_charge_id_tax` in settings VIES.
- Errore **422** con `error_code: TAX_IN_USE` (non più 500 generico su FK).
- File: `src/repository/tax_usages.py`, `TaxRepository.find_usages`, `TaxService.delete_tax`.
- Test: `tests/unit/repository/test_tax_find_usages.py`, `tests/unit/services/test_tax_service.py` (classe `TestTaxServiceDelete`), `tests/integration/api/v1/test_tax_delete.py`.

---

- Sync PS: regole tax invariate; nessun import di resolver VIES in `prestashop_service`.
- Esenzione manuale allineata a `reverse_charge_id_tax` (`app_configurations` categoria `vies`).
- Creazione ordine con `vies_status=eligible`: `id_tax` VIES su righe/spedizione senza tax esplicita.
- Test: `tests/unit/vies/test_vies_exemption_tax.py`, `tests/unit/repository/test_order_create_vies_eligible_tax.py`.

---

## Ultime modifiche (2026-05-27) — fix `vies_status` PUT/GET MySQL

**Problema:** dopo `PUT /api/v1/orders/{id}` con `"vies_status": "eligible"`, il `GET` restituiva `null`.

**Causa:** SQLAlchemy mappava l'enum MySQL con i **nomi** (`ELIGIBLE`) mentre DB/sync usano i **valori** (`eligible`).

**Fix:** `Enum(ViesStatus, values_callable=...)` in `src/models/order.py`; `OrderRepository.update` consente reset esplicito a `null`.

**Verifica:** `pytest tests/integration/api/v1/test_order_put_vies_status.py` — riavviare `uvicorn` dopo il deploy.

---

## Ultime modifiche (2026-05-27) — BE-VIES-FALLBACK-GLOBAL

**Scope:** Fallback IVA globale + reverse charge VIES (prerequisito FE-VIES-3 STEP 3).

| Metodo | Path | Descrizione |
|--------|------|-------------|
| GET | `/api/v1/taxes/global-default` | Default IVA globale (`id_country` null) |
| PUT | `/api/v1/taxes/{id}/set-country-default` | Default paese **o** globale |
| GET/PUT | `/api/v1/settings/` | Facade: legge/scrive `reverse_charge_id_tax` su `app_configurations` (category `vies`) |
| GET | `/api/v1/app_configurations/by-category/vies` | Lista configurazioni VIES |

`POST/PUT /api/v1/taxes/` accettano `id_country: null`. `/api/v1/init/` include `settings.reverse_charge_id_tax`.

Persistenza: `app_configurations` — `category=vies`, `name=reverse_charge_id_tax`, `value=<id_tax>`. Nessuna tabella `settings` dedicata.

Migration: `alembic upgrade head` (revision `20260527_0003` migra da `settings` se presente).

## Integrazione FastLDV (magazzino)

API dedicate per l’app browser FastLDV (sostituisce `checkOrderData` + `validate.php` di Smarty con **una sola GET**). Autenticazione tramite header `X-FastLDV-Key` (no JWT).

| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET | `/api/v1/fastldv/order/{code}` | Dati ordine + righe + `validation` (`200` stampabile, `422` bloccato con payload completo) |
| POST | `/api/v1/fastldv/notify-print` | Aggiorna `shipping.tracking` dopo stampa etichetta |

**Identificatori:** `id_order` = PK interna incrementale; `id_origin` = ID PrestaShop o **`0`** se ordine nato in app (non viene sostituito con `id_order`). Per ordini PS i due numeri differiscono (es. `id_origin=457300`, `id_order=48564`). Barcode `{code}`: ID PS se sync, altrimenti `id_order`. Etichetta: `document.num_doc`. Angular/SSE: sempre `id_order`.

**Nota:** la **multispedizione** (`is_multishipping`, più spedizioni per ordine) è **accantonata in v1**: GET e notify-print usano solo la spedizione principale (`orders.id_shipping`).

Variabili `.env`:

- `FASTLDV_API_KEY` — chiave obbligatoria per gli endpoint sopra
- `FASTLDV_BYPASS_VALIDATE_IDS` — (opz.) lista `id_origin` separati da virgola che saltano la validazione

Esempio smoke test:

```bash
curl -H "X-FastLDV-Key: $FASTLDV_API_KEY" "http://localhost:8000/api/v1/fastldv/order/69099?carrier=BRT+NAPOLI"
```

Guida completa: [docs/BE_FASTLDV_INTEGRATION.md](docs/BE_FASTLDV_INTEGRATION.md). Traccia implementazione BE: [.cursor/tasks_claude/fastLdv/IMPLEMENTAZIONE_TECNICA_FASTLDV.md](.cursor/tasks_claude/fastLdv/IMPLEMENTAZIONE_TECNICA_FASTLDV.md). Handoff team app magazzino: [docs/PROMPT_FASTLDV_APP_CUTOVER.md](docs/PROMPT_FASTLDV_APP_CUTOVER.md).

**Real-time tracking (BE-FASTLDV-EVT):** dopo `notify-print` il BE emette `order.tracking.updated` (payload: `id_order`, `tracking`, `awb`); FE Angular consuma `GET /api/v1/events/stream`. Handoff: [docs/FE_HANDOFF_SSE_TRACKING.md](docs/FE_HANDOFF_SSE_TRACKING.md).

**Test:** `pytest tests/unit/services/test_fastldv_order_service.py tests/integration/api/v1/test_fastldv.py tests/integration/api/v1/test_events_sse.py -v`

## Ultime modifiche (2026-06-18) — Documentazione FastLDV

**Scope:** Traccia tecnica implementazione FastLDV in `.cursor/tasks_claude/fastLdv/IMPLEMENTAZIONE_TECNICA_FASTLDV.md` (architettura, flussi, mapping, test, stato task BE-FASTLDV-1/2/EVT).

## Ultime modifiche (2026-06-12) — Fix calcolo totali preventivi

**Scope:** Correzione errore 500 su `GET /api/v1/preventivi`.

- `calculate_order_totals` / `calculate_price_with_tax`: conversione sicura di aliquote IVA `Decimal` (colonna `Tax.percentage`) in `float` prima dei calcoli.
- `OrderDocumentService.calculate_totals`: mappa aliquote normalizzata a `float`.
- Test: `tests/unit/services/test_calculate_order_totals.py`.

## Ultime modifiche (2026-06-11) — BE-FASTLDV-EVT

**Scope:** Real-time tracking verso Angular dopo stampa FastLDV.

- `EventType.ORDER_TRACKING_UPDATED` (`order.tracking.updated`) + emit in `POST /fastldv/notify-print`
- `SseFanoutService` + `GET /api/v1/events/stream` (JWT, `text/event-stream`)
- Test: `tests/integration/api/v1/test_events_sse.py`, `tests/unit/events/test_sse_fanout_service.py`

## Ultime modifiche (2026-06-09) — BE-FASTLDV-1/2

**Scope:** Fase 1 backend integrazione FastLDV (ordine unificato + notify-print).

- Router `src/routers/fastldv.py`, service `FastLdvOrderService`, auth `X-FastLDV-Key`, settings `FASTLDV_API_KEY` / `FASTLDV_BYPASS_VALIDATE_IDS`.
- `OrderRepository.get_by_origin_id(id_origin, id_store?)` con filtro opzionale multi-negozio.
- Validazione allineata a `validate.php` (priorità bypass → annullato → bloccato → non pagato → già spedito → non pronto → OK/ristampa).
- Alias legacy Smarty in risposta (`data.legacy`) per transizione adapter PHP.
- Multispedizione esplicitamente fuori scope v1 (solo `orders.id_shipping`).
- Dual lookup FastLDV: `id_origin` PrestaShop oppure `id_order` per ordini gestionale (`id_origin=0`).

## Ultime modifiche (2026-05-27) — BE-VIES-CLEANUP-SEED

**Scope:** Rimozione seed aliquote UE (BE-VIES-1) da prod/stage.

- Seed disattivato in `scripts/setup_initial.py` (attivo solo con `SEED_EU_VAT_TAXES=1` per test/CI).
- Logica seed/cleanup: `src/vies/eu_vat_seed.py`.
- Migration: `alembic upgrade head` → `20260527_0001_cleanup_be_vies_1_seed`.
- Guida: [docs/BE_VIES_CLEANUP_SEED.md](docs/BE_VIES_CLEANUP_SEED.md).

## Ultime modifiche (2026-05-27) — BE-VIES-2

**Scope:** Fase 2/4 VIES — sync PrestaShop + API gestionale.

- **Sync:** `vies_status_resolver` + bulk INSERT in `prestashop_service`; P.IVA da `vat_number` o `vat`.
- **Lista, dettaglio, creazione:** `vies_status` su `GET /api/v1/orders/`, `GET /api/v1/orders/{id}`, body/response `POST /api/v1/orders/`, body `PUT /api/v1/orders/{id}`.
- **Esenzione manuale:** `PATCH .../apply-vies-exemption`, `POST .../bulk-apply-vies-exemption`, evento `ORDER_VIES_EXEMPTION_APPLIED`.
- **Test:** `tests/unit/repository/test_order_repository_vies_filter.py`, `tests/unit/services/test_order_vies_exemption.py`, `tests/integration/api/v1/test_order_vies_exemption.py`.

## Ultime modifiche (2026-05-27) — BE-VIES-1

**Scope:** Fondamenta dati VIES — Fase 1/4.

- **Order:** enum `ViesStatus` (`eligible` \| `not_eligible`) + colonna nullable `vies_status` (popolamento in Fase 2 sync PrestaShop).
- **Tax:** riuso `Tax(id_country, is_default)` per default IVA per paese; endpoint `country-defaults`; evento `TAX_COUNTRY_DEFAULT_CHANGED`; invalidazione cache `init_data:static` / `init_data:full` su `set-country-default`.
- **Setup:** `scripts/setup_initial.py` — DDL `vies_status` + seed 27 aliquote UE (FI a 25% per limite `Tax.percentage` Integer).
- **Test:** `tests/unit/repository/test_tax_repository.py`, `tests/unit/services/test_tax_service.py`, `tests/integration/api/v1/test_tax_country_defaults.py`, `tests/scripts/test_setup_initial_eu_taxes.py`.

---

## API — Borderò spedizioni

| Metodo | Path | Descrizione |
|--------|------|-------------|
| POST | `/api/v1/bordero/generate` | PDF riepilogo spedizioni in stato **Spediti** (`id_order_state=3`) per `carriers_api.id_carrier_api`, con tracking valorizzato |

**Body:** `{ "carrier_id": int, "update_status": bool, "date_from"?: "YYYY-MM-DD", "date_to"?: "YYYY-MM-DD" }`

**Header risposta (PDF blob):**

| Header | Descrizione |
|--------|-------------|
| `X-Bordero-Order-Count` | Spedizioni incluse nel PDF |
| `X-Bordero-Order-Ids` | CSV `id_order` inclusi |
| `X-Bordero-Hint-Code` | Solo se count=0: `MISSING_TRACKING`, `NO_ORDERS_FOR_CARRIER`, `INACTIVE_CARRIER`, `GENERIC` |
| `X-Bordero-Hint-Message` | Messaggio operatore in italiano, URL-encoded (`decodeURIComponent` in FE) |
| `X-Bordero-Missing-Tracking-Count` | Ordini Spediti con corriere corretto ma senza AWB |

Permesso RBAC: `shipments.create`. Test: `tests/integration/api/v1/test_bordero.py`.

---

## API — DDT PDF

Prefisso `/api/v1/ddt`. Permesso RBAC: `ddt.read`.

| Metodo | Path | Descrizione |
|--------|------|-------------|
| GET | `/api/v1/ddt/pdf/{id_order_document}` | PDF Documento di Trasporto (`Content-Disposition: attachment`) |

Identificatore: PK gestionale `id_order_document` (non `id_order`).

Handoff FE: [docs/FE_HANDOFF_DDT_PRINT_PDF.md](docs/FE_HANDOFF_DDT_PRINT_PDF.md) — prompt chat: [.cursor/tasks_claude/prompt_FE_ddt_print_pdf.md](.cursor/tasks_claude/prompt_FE_ddt_print_pdf.md).

---

## Ultime modifiche (2026-06-18) — Backlog FatturaPA implementazione

Creato backlog operativo dei task ancora da sviluppare per FatturaPA (gap analysis rispetto al codice esistente):

- [`.cursor/tasks_claude/fatturapa_backlog_implementazione.md`](.cursor/tasks_claude/fatturapa_backlog_implementazione.md) — task P0–P3, ordine di implementazione, checklist go-live
- Piano tecnico di riferimento: [`.cursor/tasks_claude/fatturapa_riassunto_piano.md`](.cursor/tasks_claude/fatturapa_riassunto_piano.md)

---

## Ultime modifiche (2026-06-18) — Riconciliazione backlog BE

Backlog unificato allineato allo stato del codice: [`.cursor/tasks_claude/BACKLOG_UNIFICATO.md`](.cursor/tasks_claude/BACKLOG_UNIFICATO.md).

**Chiusi:** BE-FASTLDV-1/2, BE-FASTLDV-EVT (implementazione), BE-ALIQ-02..05, BE-TAX-DECIMAL, BE-RETURN-PRICE-FIX.

**Ancora aperti (BE):** REPLAN-AS400-PR7, BE-FASTLDV-3 (opz.), BE-FASTLDV-EVT (QA), BE-ALIQ-06/07/08, BE-1, BE-TAX-DEFINE-FIX, BE-VIES-4, BE-INFRA-ALEMBIC, T1.

---

## Ultime modifiche (2026-06-16) — Fix calcolo righe reso (doppia IVA)

- **Problema:** in creazione/aggiornamento reso, se il FE inviava `unit_price` con l'importo **con IVA** dell'ordine (es. 289,97 €), il backend lo trattava come imponibile e ricalcolava l'IVA (totale errato, es. 363,91 € invece di 289,97 €).
- **Fix:** helper `resolve_return_unit_prices` in `src/services/core/tool.py` — se `unit_price` coincide con `order_detail.unit_price_with_tax`, usa `unit_price_net` dell'ordine originale. Applicato in `FiscalDocumentService.create_return`, `FiscalDocumentRepository.create_return`, `calculate_return_totals` e `update_fiscal_document_detail`.
- Test: `tests/unit/services/core/test_resolve_return_unit_prices.py`.

---

## Ultime modifiche (2026-06-16) — Fix PDF DDT (Fase 1 + 2)

- **Fase 1 — Fix 500:** conversione esplicita `Decimal` → `float` in `DDTPDFService` e serializzazione spedizione in `DDTService.get_ddt_complete` (allineato al preventivo). Router con `try/except` 404/500.
- **Fase 2 — Correttezza layout:** IVA righe risolta via `TaxRepository.get_percentage_by_id` (non più `id_tax` come percentuale). Totali riga con sconto `%` / importo. Colli da `packages` (fallback `1`). Riepilogo IVA con aliquota dominante dalle righe.
- Test: `tests/unit/services/pdf/test_ddt_pdf_service.py`.

---

## Ultime modifiche (2026-06-15) — Stampa PDF singolo ordine

- Nuovo endpoint `GET /api/v1/orders/{id}/pdf` con layout allineato al documento ordine elettronew (logo + anagrafica, barcode Code39, blocchi Intestazione / Indirizzo di consegna, tabella righe con Impon./IVA/Sconto, riepilogo totali a destra).
- Servizio: `src/services/pdf/order_pdf_service.py`; orchestrazione in `OrderService.generate_order_pdf`.
- Permesso RBAC: `orders.read`. Risposta: PDF inline (`Content-Disposition: inline`).
- **Fix righe ordine (2026-06-15):** query PDF include `id_order_document IS NULL OR = 0` (sync PrestaShop salva `0`, non NULL).
- **Layout tabella righe:** colonne ribilanciate (Codice 40 mm, troncatura per larghezza con `get_string_width`, descrizione su max 2 righe).
- Handoff FE: [docs/FE_HANDOFF_ORDER_PRINT_PDF.md](docs/FE_HANDOFF_ORDER_PRINT_PDF.md) — prompt chat: [.cursor/tasks_claude/prompt_FE_order_print_pdf.md](.cursor/tasks_claude/prompt_FE_order_print_pdf.md).

---

## Ultime modifiche (2026-06-15) — Borderò hint diagnostici (count=0)

- Quando `X-Bordero-Order-Count=0`, la risposta include header `X-Bordero-Hint-*` con la causa reale (es. ordini Spediti **senza tracking** vs assenza ordini per corriere).
- Il FE può mostrare `X-Bordero-Hint-Message` invece del messaggio generico "nessun ordine per questo corriere".
- File: `OrderRepository.get_bordero_zero_hints`, `BorderoService`, `src/routers/bordero.py`.

---

## Documentazione

- [DOCUMENTAZIONE.md](DOCUMENTAZIONE.md) – panoramica e architettura  
- [QUICK_START.md](QUICK_START.md) – avvio rapido e comandi  
- [docs/](docs/) – guide specifiche (eventi, plugin, sync, ecc.)
- [.cursor/tasks_claude/BACKLOG_UNIFICATO.md](.cursor/tasks_claude/BACKLOG_UNIFICATO.md) – backlog unificato FE+BE (fonte di verità task; riconciliato 2026-06-18)
- [.cursor/tasks_claude/fatturapa_backlog_implementazione.md](.cursor/tasks_claude/fatturapa_backlog_implementazione.md) – task FatturaPA da implementare (P0–P3, go-live)
- [.cursor/tasks_claude/fatturapa_riassunto_piano.md](.cursor/tasks_claude/fatturapa_riassunto_piano.md) – riassunto normativa FatturaPA e piano fasi
- [docs/BE_FASTLDV_INTEGRATION.md](docs/BE_FASTLDV_INTEGRATION.md) – integrazione app magazzino FastLDV
