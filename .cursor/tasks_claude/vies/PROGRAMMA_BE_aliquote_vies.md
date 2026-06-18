# Programma di lavoro — BE Aliquote IVA + VIES

> Derivato da `prompt_BE_aliquote_vies.md` + audit codice.  
> **Aggiornato 2026-06-03 (v2)** — regole prodotto definitive (sync invariato; VIES non invasiva).

---

## Regole prodotto (vincolanti)

### 1) Sync PrestaShop — **nessuna modifica alle regole attuali**

- La logica tax/sync esistente in `prestashop_service` **resta com’è** (mappa paese, ricalcolo netti, ecc.).
- **Vietato** applicare logica VIES in import: niente `resolve_tax_id_for_delivery`, niente reverse charge automatico, niente ricalcolo righe per `vies_status == eligible`.
- Consentito: **snapshot** `orders.vies_status` (solo metadato per filtri/UI).

### 2) Logica VIES — **solo due ingressi**

| Ingresso | Comportamento |
|----------|----------------|
| **Rettifica manuale** KO → OK | `PATCH/POST apply-vies-exemption` — righe 0%, totale ivato invariato, `vies_status=eligible` |
| **Creazione esplicita** ordine VIES OK in app | `POST /orders` con `vies_status: eligible` — righe senza `id_tax` ricevono aliquota VIES (`reverse_charge_id_tax` o fallback 0%) |

### 3) Tutto il resto — flusso ordinario

- Creazione ordine **senza** `vies_status: eligible` → nessun ramo VIES del resolver.
- Update ordine, sync, documenti da ordine importato → **non** applicare VIES in automatico.
- `resolve_tax_id_for_delivery` (default paese/globale) — **fuori scope** finché non serve per altri flussi app espliciti; **non** su sync.

### 4) Task **non in scope**

| Task | Stato |
|------|--------|
| **BE-ALIQ-01S** (sync “copia fedele” PS) | ❌ Annullato — regole sync non si cambiano |
| **BE-ALIQ-01** (resolver su tutte le creazioni app) | 🔻 Ridotto → solo creazione `eligible` esplicita |
| **BE-ALIQ-08** (`define_tax`) | 🟡 Opzionale — non bloccante se sync/ordini ordinari restano invariati |

---

## Obiettivo programma (v2)

1. Garantire che **nessun codice** applichi VIES in sync/update silenziosi.
2. **BE-ALIQ-01M** — esenzione manuale usa `reverse_charge_id_tax`.
3. **BE-ALIQ-01** — creazione ordine con `vies_status=eligible` imposta `id_tax` VIES sulle righe senza `id_tax`.
4. Hardening: delete tax, cache, serializzazione, API opzionale, DECIMAL.

---

## Sommario fasi

| Fase | ID task | Priorità | Stima |
|------|---------|----------|-------|
| 0 | BE-ALIQ-00 | ✅ chiuso (audit) | — |
| 1 | **BE-ALIQ-01M**, **BE-ALIQ-01** | 🔴 in corso | 1 gg |
| 1 | BE-ALIQ-02, BE-ALIQ-08 | 🔴 | 1 gg |
| 2 | BE-ALIQ-03, 04 | 🟡 | 1 gg |
| 3 | BE-ALIQ-07 | 🟢 opzionale | 1–2 gg |
| 4 | BE-ALIQ-05, 06 | 🟡/🟢 | 2–4 gg |

**Ordine:** `01M → 01 → 02 → [08] → 03 → 04 → …`

---

## BE-ALIQ-00 — Inventario ✅

**Esito audit:**

- `resolve_tax_id_for_delivery` — solo test; **sync non lo chiama** ✓
- Sync — snapshot `vies_status` senza branch VIES su prezzi/`id_tax` ✓
- Gap da chiudere: `apply-vies-exemption` → `reverse_charge`; create `eligible` → `id_tax` righe

---

## BE-ALIQ-01M — Esenzione manuale VIES ✅

**Unico percorso** rettifica ordine esistente (import o gestionale).

- [x] `resolve_vies_exemption_tax_id_with_fallback` in `apply_vies_exemption`
- [x] Test `test_uses_reverse_charge_from_settings`

---

## BE-ALIQ-01 — Creazione ordine `vies_status=eligible` esplicita ✅

**Solo** quando il client passa `vies_status: eligible` su `POST /orders`:

- [x] Righe senza `id_tax` → aliquota VIES (`order_repository.create`)
- [x] `generate_shipping` eligible → stessa aliquota
- [x] Test `test_order_create_vies_eligible_tax.py`
- [x] `test_no_vies_tax_in_prestashop_sync.py`

**Fuori scope:** resolver su create `not_eligible`, preventivi, DDT, update riga.

**Prossimo BE:** BE-ALIQ-02 (delete tax strutturato).

**FE (repo gestionale):** pulsante KO → OK — vedi [docs/FE_VIES_APPLY_EXEMPTION_BUTTON.md](../../docs/FE_VIES_APPLY_EXEMPTION_BUTTON.md).

---

## BE-ALIQ-01S — ~~Sync fedele PS~~ ❌ ANNULLATO

Non modificare regole sync attuali. Vedi §1.

---

## BE-ALIQ-02 — Delete Tax `TAX_IN_USE` 🔴

(ineserito — vedi versione precedente del documento)

---

## BE-ALIQ-03 / 04 / 05 / 06 / 07

(ineseriti — vedi versione precedente del documento)

---

## Matrice wiring (v2)

| Flusso | Tipo | Logica VIES |
|--------|------|-------------|
| Sync PrestaShop | SYNC_INVARIATO | ❌ Solo `vies_status` snapshot |
| `apply-vies-exemption` | AZIONE_MANUALE | ✅ |
| `POST /orders` + `vies_status=eligible` | CREAZIONE_ESPLICITA | ✅ `id_tax` righe senza tax |
| `POST /orders` senza eligible | ORDINARIO | ❌ |
| PUT ordine / update righe | ORDINARIO | ❌ |
| Documenti da ordine | EREDITA | ❌ |

---

## Sprint corrente

1. ~~BE-ALIQ-00~~ ✅  
2. **BE-ALIQ-01M + BE-ALIQ-01** (questa sessione)  
3. BE-ALIQ-02  
4. BE-ALIQ-03  

---

## Comandi verifica

```bash
pytest tests/unit/services/test_order_vies_exemption.py \
       tests/unit/vies/test_vies_exemption_tax.py \
       tests/unit/repository/test_order_create_vies_eligible_tax.py -v
rg "resolve_tax_id_for_delivery|get_vies_exemption_tax_id" src/services/ecommerce -n
```

---

## Riferimenti

- `src/vies/tax_resolution.py` — `get_vies_exemption_tax_id`, `is_vies_eligible_status`
- `src/services/routers/order_service.py` — `apply_vies_exemption`
- `src/repository/order_repository.py` — `create`, `generate_shipping`
