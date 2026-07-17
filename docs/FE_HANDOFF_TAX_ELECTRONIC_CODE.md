# FE Handoff — Tax `electronic_code` + `note` (FatturaPA Natura)

Guida per il gestionale Angular (repo FE separato).  
Backend: **ECommerceManagerAPI** — migration applicata, step 1 FatturaPA completato (2026-06-22).

---

## Contesto

Un handoff precedente chiedeva di inviare in `electronic_code` il formato concatenato:

```
N3.1 - Non imponibili - esportazioni
```

Quel formato **non è più valido** per il BE/FatturaPA.

FatturaPA distingue due tag XML:

| Tag XML | Contenuto | Campo API Tax |
|---------|-----------|---------------|
| `<Natura>` | Solo codice breve (`N3.1`, `N3.2`, …) | `electronic_code` |
| `<RiferimentoNormativo>` | Testo normativo / descrizione | `note` |

Il FE deve quindi persistere **codice** e **descrizione su campi separati**.

---

## Contratto campi

| Campo | Tipo | Max length | Obbligatorio | Esempio |
|-------|------|------------|--------------|---------|
| `electronic_code` | `string` | 255 | No (consigliato se `percentage = 0`) | `N3.1` |
| `note` | `string` | 200 | No | `Non imponibili - esportazioni` |

### Formato `electronic_code` (codice natura)

Valori ammessi dal BE in generazione FatturaPA (regex):

```
N[1-7](.[0-9]+)?
```

Esempi validi: `N1`, `N2`, `N3.1`, `N3.2`, `N4`, `N6.9`, `N7`  
Esempi **non validi** per FatturaPA (il BE li ignora in XML):

- `N3.1 - Non imponibili - esportazioni` ❌
- `Non imponibili` ❌
- `E123` ❌

> **Nota:** l’API Tax accetta qualsiasi stringa ≤255 caratteri in `electronic_code` (nessun validator Pydantic sul pattern). La validazione formato è responsabilità FE + uso FatturaPA lato BE.

---

## API coinvolte

| Metodo | Endpoint | Note |
|--------|----------|------|
| `POST` | `/api/v1/taxes/` | Creazione aliquota |
| `PUT` | `/api/v1/taxes/{id_tax}` | Modifica |
| `GET` | `/api/v1/taxes/` | Lista (paginata) |
| `GET` | `/api/v1/taxes/{id_tax}` | Dettaglio |
| `GET` | `/api/v1/init/?include=static` | Cache init — array `taxes[]` |

Permessi RBAC: `tax` + `create` / `update` / `read` (come già in uso).

---

## Payload — creazione (corretto)

```http
POST /api/v1/taxes/
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "id_country": 51,
  "is_default": 0,
  "name": "Esportazioni extra-UE",
  "note": "Non imponibili - esportazioni",
  "percentage": 0,
  "electronic_code": "N3.1"
}
```

**Response 201** (campi rilevanti):

```json
{
  "id_tax": 42,
  "id_country": 51,
  "is_default": 0,
  "name": "Esportazioni extra-UE",
  "note": "Non imponibili - esportazioni",
  "percentage": 0,
  "electronic_code": "N3.1"
}
```

---

## Payload — da NON inviare più

```json
{
  "electronic_code": "N3.1 - Non imponibili - esportazioni"
}
```

Causava `400 Data too long` prima della migration; oggi verrebbe salvato ma **non comparirebbe** in FatturaPA (`<Natura>` ignorato se formato non valido).

---

## Payload — modifica

```http
PUT /api/v1/taxes/42
```

```json
{
  "id_country": 51,
  "is_default": 0,
  "name": "Esportazioni extra-UE",
  "note": "Non imponibili - esportazioni art. 8 DPR 633/72",
  "percentage": 0,
  "electronic_code": "N3.1"
}
```

---

## Init / lista taxes

`GET /api/v1/init/?include=static` restituisce ogni tax con entrambi i campi separati:

```json
{
  "taxes": [
    {
      "id_tax": 42,
      "name": "Esportazioni extra-UE",
      "percentage": 0,
      "electronic_code": "N3.1",
      "note": "Non imponibili - esportazioni",
      "id_country": 51,
      "is_default": 0
    }
  ]
}
```

Nessun troncamento: il valore completo di `note` e `electronic_code` è restituito così com’è in DB.

---

## Suggerimenti UI (FE)

### Select «Codice natura»

Se la sorgente dati è una lista predefinita (es. tabella codici natura Agenzia Entrate):

| value (→ `electronic_code`) | label (solo UI) | → `note` (precompilabile) |
|-----------------------------|-----------------|---------------------------|
| `N3.1` | N3.1 — Non imponibili - esportazioni | `Non imponibili - esportazioni` |
| `N3.2` | N3.2 — Non imponibili - cessioni intracomunitarie | `Non imponibili - cessioni intracomunitarie` |
| `N3.2` | N3.2 — Non soggette (art. 41 DL 331/93) | testo normativo VIES |

- **`electronic_code`** = solo `value` (codice breve).
- **`note`** = descrizione normativa (editabile dall’utente, precompilata dalla label senza il prefisso codice).

### Form aliquota IVA 0%

Quando `percentage === 0`:

- mostrare select/input `electronic_code` (obbligatorio consigliato);
- mostrare textarea `note` per riferimento normativo;
- in stampa documenti/PDF usare entrambi: codice in colonna natura, descrizione in nota/riferimento.

### Aliquote con IVA > 0

`electronic_code` e `note` possono restare vuoti (campo `Natura` non richiesto se aliquota > 0).

---

## Dati esistenti / migrazione FE

Se in DB o in cache locale ci sono valori legacy concatenati in `electronic_code`:

```
N3.1 - Non imponibili - esportazioni
```

Al prossimo edit in FE:

1. splittare al primo ` - ` (spazio-trattino-spazio);
2. salvare parte sinistra in `electronic_code`;
3. salvare parte destra in `note` (se `note` vuota).

Script one-shot lato FE opzionale; il BE **non** migra automaticamente i dati esistenti.

---

## Cosa fa il BE (FatturaPA — step 1, già live)

In generazione XML fattura elettronica:

- `<Natura>` ← `Tax.electronic_code` normalizzato (solo codice breve);
- `<RiferimentoNormativo>` ← `Tax.note` (se presente);
- fix crash `.2f` su stringa eliminato.

**Implementato (2026-07-17, BE-PA-P0-05):**

- Natura/aliquota **per riga** da `id_tax` ordine.
- Override automatico VIES → `N3.2` su ordini `vies_status=eligible` (righe prodotto).
- `DatiRiepilogo` multi-aliquota (es. prodotti 0% + spedizione 22%).

Vedi [`docs/FATTURAPA.md`](../FATTURAPA.md) §7 e `src/services/external/fatturapa_tax_line.py`.

---

## Acceptance criteria FE

1. Creazione aliquota: `POST /taxes/` con `electronic_code: "N3.1"` e `note: "Non imponibili - esportazioni"` → **201**.
2. Modifica: `PUT /taxes/{id}` con stessa struttura → **200**.
3. Init e GET restituiscono codice e nota **separati**, senza concatenazione.
4. UI select natura: invia solo codice in `electronic_code`, descrizione in `note`.
5. Nessun invio del formato `"N3.1 - ..."` in `electronic_code`.
6. (Consigliato) Validazione client sul pattern `N[1-7](\.\d+)?` prima del submit.

---

## Test BE di riferimento

```bash
pytest tests/integration/api/v1/test_tax_electronic_code_length.py -v
pytest tests/unit/services/external/test_fatturapa_natura.py -v
```

---

## Riferimenti

- README BE: sezione «Ultime modifiche (2026-06-22) — taxes.electronic_code + FatturaPA Natura»
- Helper BE: `src/services/external/fatturapa_natura.py`
- Schema: `src/schemas/tax_schema.py` (`TaxSchema`, `TaxResponseSchema`)
