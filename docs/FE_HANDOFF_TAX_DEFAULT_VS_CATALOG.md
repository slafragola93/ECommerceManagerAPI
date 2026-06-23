# FE Handoff — Aliquote IVA vs Default per paese (`is_default`)

Guida per il gestionale Angular (repo FE separato).  
Backend: **ECommerceManagerAPI** — nessuna migration richiesta; chiarimento contratto e UX (2026-06-22).

---

## Problema segnalato

Nella sezione **Impostazioni → Aliquote IVA** è possibile creare più aliquote assegnate allo stesso paese, ma l’UI sembra permettere l’“attivazione” di **una sola** aliquota per paese: attivando una seconda, la prima risulta disattivata.

**Comportamento atteso dal prodotto:**

- Più aliquote per lo stesso paese devono restare **utilizzabili** (es. 22%, 10%, 0% N3.1 per IT).
- Il **default automatico** per paese (es. IVA standard 22% IT) è un concetto **separato**: una sola aliquota “standard” per paese, usata quando il sistema risolve l’IVA senza `id_tax` esplicito.
- Cambiare quale aliquota è default **non** deve essere l’unico modo per “rendere disponibile” un’aliquota nel catalogo.

---

## Causa root (backend)

Non esiste un campo `is_active` su `Tax`. L’unico flag di stato rilevante è **`is_default`** (0 | 1).

| Flag | Significato BE | Vincolo |
|------|----------------|---------|
| `is_default = 1` | Aliquota **default automatica** per scope paese (o globale se `id_country` null) | **Al massimo una** per `id_country` |
| `is_default = 0` | Aliquota nel catalogo, **selezionabile manualmente** via `id_tax` | Nessun limite per paese |

Se il FE usa `is_default` come toggle “Attiva / Disattiva aliquota”, si innesca la logica BE che garantisce un solo default per paese (`set_country_default_atomic` / `_apply_default_invariant`): impostare `is_default=1` su aliquota B azzera `is_default` su tutte le altre dello stesso paese.

**Non è un bug BE:** è il vincolo voluto per la risoluzione automatica IVA (VIES / ordini senza tax esplicita).

---

## Due tab UI, una tabella DB

Entrambe le sezioni operano sulla stessa entità `taxes`. Non sono due cataloghi separati.

```
┌─────────────────────────────┐     ┌──────────────────────────────┐
│  Tab "Aliquote IVA"         │     │  Tab "Default per paese"     │
│  Catalogo completo          │     │  Mappa paese → standard IVA  │
├─────────────────────────────┤     ├──────────────────────────────┤
│  CRUD tutte le aliquote     │     │  Solo is_default=1 + paese   │
│  Molte per stesso paese OK  │     │  Una standard per paese      │
│  Permessi: tax.*            │     │  Permessi: settings.*        │
└─────────────────────────────┘     └──────────────────────────────┘
              │                                    │
              └────────────── taxes ──────────────┘
```

### Tab Aliquote IVA — catalogo

**Scopo:** creare e mantenere tutte le aliquote (nome, %, paese, `electronic_code`, `note`).

| Metodo | Endpoint | RBAC |
|--------|----------|------|
| GET | `/api/v1/taxes/` | `tax.read` |
| POST | `/api/v1/taxes/` | `tax.create` |
| PUT | `/api/v1/taxes/{id_tax}` | `tax.update` |
| DELETE | `/api/v1/taxes/{id_tax}` | `tax.delete` |
| GET | `/api/v1/init/?include=static` | — → `taxes[]` completo |

**Uso:** dropdown su righe ordine/documento, scelta manuale `id_tax`, configurazione FatturaPA (`electronic_code`).

### Tab Default per paese — configurazione automatica

**Scopo:** definire quale aliquota applicare **in automatico** per paese di consegna quando non c’è `id_tax` esplicito.

| Metodo | Endpoint | RBAC |
|--------|----------|------|
| GET | `/api/v1/taxes/country-defaults` | `settings.read` |
| GET | `/api/v1/taxes/country-defaults/{iso_code}` | `settings.read` |
| PUT | `/api/v1/taxes/{id_tax}/set-country-default` | `settings.update` |
| GET | `/api/v1/taxes/global-default` | `settings.read` |

**Uso BE:** `resolve_tax_id_for_delivery()` → default paese → default globale; seed IVA UE; fallback ordini nuovi senza tax.

---

## Cosa deve fare il FE (checklist)

### 1. Non usare `is_default` come “Attiva aliquota”

| Azione UI | ❌ Sbagliato | ✅ Corretto |
|-----------|-------------|------------|
| Creare aliquota IT 10% | `POST` con `is_default: 1` | `POST` con `is_default: 0` |
| “Attivare” aliquota in catalogo | `PUT` con `is_default: 1` | Nessun toggle attivo/disattivo su `is_default`; l’aliquota esiste = selezionabile |
| Impostare IVA standard IT | Toggle generico su riga catalogo | Azione dedicata → `PUT .../set-country-default` **oppure** tab Default per paese |
| Mostrare stato in lista catalogo | Badge “Attiva” da `is_default` | Badge **“Default paese”** solo se `is_default === 1`; altrimenti nessun badge obbligatorio |

### 2. Dropdown aliquote su ordini / documenti

Filtrare per contesto operativo, **non** per `is_default`:

```typescript
// Esempio: aliquote selezionabili per paese consegna IT
taxes.filter(t => t.id_country === idCountryDelivery || t.id_country == null)
```

Tutte le aliquote con `is_default=0` restano nel catalogo e in `init.taxes[]` — **non sono disattivate**.

### 3. Tab Default per paese

- Mostrare solo aliquote con `is_default=1` (da `GET /country-defaults`) o evidenziare in griglia paese → aliquota standard.
- Azione “Imposta come default” → **solo** `PUT /api/v1/taxes/{id_tax}/set-country-default`.
- Messaggio UX esplicito: *“Stai cambiando l’aliquota standard automatica per {paese}. Le altre aliquote restano disponibili per selezione manuale.”*

### 4. Creazione aliquota

Payload consigliato (catalogo, non default):

```json
{
  "id_country": 51,
  "is_default": 0,
  "name": "IVA IT 10% ridotta",
  "percentage": 10,
  "electronic_code": "",
  "note": ""
}
```

Impostare default **solo** se l’utente usa il flusso dedicato (tab Default per paese / azione “Imposta default”).

---

## Flussi di risoluzione IVA (riferimento BE)

```
Ordine / riga con id_tax esplicito     →  usa id_tax scelto (qualsiasi dal catalogo)
Ordine senza id_tax + VIES eligible    →  reverse_charge_id_tax (settings VIES)
Ordine senza id_tax + paese consegna   →  tax con is_default=1 per id_country
Fallback                               →  tax globale (id_country null, is_default=1)
```

Il FE **non** deve limitare la scelta manuale al solo default paese.

---

## Verifica rapida (QA)

1. Creare **IVA IT 22%** (default) e **IVA IT 10%** (`is_default: 0`) — entrambe visibili in catalogo.
2. Su riga ordine IT, dropdown deve mostrare **22% e 10%** (e altre IT se presenti).
3. `PUT .../set-country-default` sulla 10% → solo la 22% perde badge default; la 10% diventa default; **entrambe** restano in `GET /taxes/` e in `init.taxes[]`.
4. Creare **IVA IT 0% N3.1** con `is_default: 0` → selezionabile su riga senza toccare il default 22%.

---

## Riferimenti BE

- Modello: `src/models/tax.py`
- Service: `src/services/routers/tax_service.py` (`_apply_default_invariant`, `set_country_default`)
- Router: `src/routers/tax.py`
- Risoluzione automatica: `src/vies/tax_resolution.py`
- Test integrazione: `tests/integration/api/v1/test_tax_country_defaults.py`
- Handoff correlato FatturaPA: [FE_HANDOFF_TAX_ELECTRONIC_CODE.md](./FE_HANDOFF_TAX_ELECTRONIC_CODE.md)

---

## Domande aperte per allineamento FE

1. Oggi il toggle “attiva” in catalogo invia `is_default: 1` su create/update?
2. Serve un vero stato “disattivata” (nascosta dai dropdown ma non eliminata)? Se sì, va richiesto al BE un campo `is_active` — **non esiste oggi**.
3. La tab Default per paese duplica azioni già presenti in catalogo?
