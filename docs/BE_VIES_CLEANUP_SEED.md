# BE-VIES-CLEANUP-SEED — Rimozione seed aliquote UE

## Contesto

Il seed **BE-VIES-1** (`scripts/setup_initial.py`, funzione `setup_eu_country_taxes`) inseriva in `taxes` un default IVA per ogni paese UE con nota:

`Standard VAT {ISO} (BE-VIES-1 seed)`

In **produzione/stage** le aliquote devono essere create dall'utente dalla UI `/tax`.

## Seed runner (disattivato)

| Elemento | Path |
|----------|------|
| Funzione seed | `src/vies/eu_vat_seed.py` → `setup_eu_country_taxes()` |
| Invocazione setup | `scripts/setup_initial.py` → solo se `SEED_EU_VAT_TAXES=1` |
| Test CI | `tests/scripts/test_setup_initial_eu_taxes.py` (chiama la funzione direttamente) |

**Default:** `SEED_EU_VAT_TAXES` non impostato → nessun seed su `python scripts/setup_initial.py`.

## Migration cleanup

| File | Revision |
|------|----------|
| `alembic/versions/20260527_0001_cleanup_be_vies_1_seed.py` | `20260527_0001` (after `0a615ed0ec5f`) |

### Applicare

```bash
alembic upgrade head
```

### Criterio DELETE (strategy conservativa)

- `note LIKE '%BE-VIES-1 seed%'` **oppure** `note LIKE 'Standard VAT %(BE-VIES-1 seed)'`
- **Esclusi** `id_tax` referenziati da `order_details`, `fiscal_document_details`, `shippings` (se la tabella esiste)

Idempotente: seconda esecuzione → 0 righe eliminate.

### Rollback

```bash
alembic downgrade -1
```

Il `downgrade()` richiama `setup_eu_country_taxes()` (idempotente). **Usare solo in emergenza** su stage; in prod preferire ricreazione manuale da UI.

Alternativa manuale senza Alembic:

```bash
SEED_EU_VAT_TAXES=1 python scripts/setup_initial.py
```

(solo la parte seed; il resto del setup è idempotente)

## Verifica post-deploy

```sql
SELECT COUNT(*) FROM taxes WHERE note LIKE '%BE-VIES-1 seed%';
-- atteso: 0 (o solo righe ancora referenziate da ordini)

GET /api/v1/init/  -- taxes[] senza righe seed
GET /api/v1/taxes/country-defaults  -- vuoto finché l'utente non configura
```

## Diagnostica SQL (locale)

Tabella: **`taxes`** (non `tax`). FK ordini: **`order_details`**.

```sql
SELECT COUNT(*) FROM taxes WHERE note LIKE '%BE-VIES-1 seed%';

SELECT t.id_tax, t.name, t.note, c.iso_code
FROM taxes t
LEFT JOIN countries c ON c.id_country = t.id_country
WHERE t.note LIKE '%BE-VIES-1 seed%'
ORDER BY c.iso_code;
```
