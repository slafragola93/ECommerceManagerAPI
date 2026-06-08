# Prompt di sessione — BE FastAPI: Aliquote IVA + VIES (ECommerceManagerAPI)

## Contesto progetto

Backend **FastAPI + MySQL + SQLAlchemy** per e-commerce (ordini, documenti fiscali, sync PrestaShop). Architettura obbligatoria: **Router → Service → Repository → Model**. DI via `src/core/container.py` + `container_config.py` — mai istanziare service/repo nei router.

Leggi `CLAUDE.md` e `README.md` per comandi e convenzioni.

---

## Modello `Tax` esistente

`src/models/tax.py`: `id_tax`, `id_country` (nullable FK), `is_default` (bool/int), `percentage` (Integer — limite storico), `name`, …

Regole business attive:
- Un solo `is_default=1` per scope: stesso `id_country` OPPURE scope globale (`id_country IS NULL`)
- Nome tax univoco (case insensitive) su create/update
- `percentage` è `int` (FI arrotondato a 25 invece di 25.5)
- Permessi tax defaults: modulo `settings`, non `taxes`

---

## Regole prodotto (2026-06-03 v2) — vincolanti

1. **Sync PrestaShop:** **non modificare** le regole tax/sync attuali; **nessuna** logica VIES che sovrascriva prezzi/`id_tax` in import.
2. **Snapshot:** `vies_status` in sync solo informativo (filtri/UI).
3. **Logica VIES attiva solo su:**
   - `apply-vies-exemption` (rettifica manuale KO → OK);
   - `POST /orders` con **`vies_status: eligible` esplicito** (righe senza `id_tax` → aliquota VIES).
4. **Non** usare resolver VIES su sync, update ordine, o create ordine senza `eligible` esplicito.

Dettaglio: `PROGRAMMA_BE_aliquote_vies.md` — **BE-ALIQ-01S annullato**.

---

## Stato implementato — NON rifare da zero

### BE-VIES-1 — Default per paese ✅
- `GET /api/v1/taxes/country-defaults`
- `GET /api/v1/taxes/country-defaults/{iso_code}`
- `PUT /api/v1/taxes/{id_tax}/set-country-default` — atomico
- `TaxService`: `list_country_defaults`, `get_default_by_country_iso`, `set_country_default`, evento `TAX_COUNTRY_DEFAULT_CHANGED`, invalidazione cache `init_data:static` / `init_data:full`
- `TaxRepository`: `get_default_by_country`, `get_default_by_country_iso`, `list_country_defaults`, `set_country_default_atomic`
- Schema: `TaxCountryDefaultResponseSchema` con `country_iso_code`, `country_name`
- `/api/v1/init/` espone già `taxes[]` con `id_country`, `is_default`

### BE-VIES-CLEANUP-SEED ✅
- `src/vies/eu_vat_seed.py` — non eseguito di default in `scripts/setup_initial.py`
- Solo con env `SEED_EU_VAT_TAXES=1` (test/CI)
- Migration: `20260527_0001_cleanup_be_vies_1_seed`

### BE-VIES-FALLBACK-GLOBAL ✅
- CRUD Tax con `id_country: null` (tax "globale")
- `GET /api/v1/taxes/global-default`
- `PUT .../set-country-default` gestisce anche scope globale → `set_global_default_atomic`
- `GET/PUT /api/v1/settings/` con `reverse_charge_id_tax` (`SettingsService`, `src/routers/settings.py`)
- Persistenza: `src/vies/vies_app_configuration.py` — `category=vies`, `name=reverse_charge_id_tax` su `app_configurations`
- `GET /api/v1/app_configurations/by-category/vies`
- `init` include `settings.reverse_charge_id_tax`
- Migration dati: `20260527_0003`

### Risoluzione aliquota ✅
`src/vies/tax_resolution.py` → `resolve_tax_id_for_delivery(session, id_country_delivery, vies_status)`:
1. `vies_status == eligible` → `get_reverse_charge_id_tax(session)`
2. Default paese consegna (`is_default=1`, `id_country`)
3. Default globale (`id_country IS NULL`, `is_default=1`)
4. `None`

### Ordini VIES ✅
- `orders.vies_status` enum: `eligible` | `not_eligible` (nullable)
- Fix SQLAlchemy: `Enum(ViesStatus, values_callable=...)` in `src/models/order.py`
- API: filtro lista, `PATCH .../apply-vies-exemption`, bulk, sync PrestaShop via `vies_status_resolver`

---

## Test esistenti

```bash
pytest tests/unit/vies/test_tax_resolution.py \
       tests/integration/api/v1/test_tax_country_defaults.py \
       tests/unit/services/test_tax_service.py \
       tests/unit/services/test_tax_global_default.py \
       tests/unit/services/test_settings_reverse_charge.py \
       tests/unit/vies/test_vies_app_configuration.py \
       tests/scripts/test_setup_initial_eu_taxes.py \
       -v
```

---

## Programma di lavoro consolidato

Vedi **[PROGRAMMA_BE_aliquote_vies.md](./PROGRAMMA_BE_aliquote_vies.md)** — fasi, sprint, matrice wiring, ID `BE-ALIQ-xx` (evita collisione con `BE-1` profilo nel BACKLOG).

---

## Piano di lavoro — task prioritizzati

### TASK BE-1 — Audit wiring `resolve_tax_id_for_delivery` su tutti i flussi 🔴 BLOCCANTE

**Obiettivo:** garantire che ogni punto del codebase che assegna `id_tax` a una riga ordine o documento passi per `resolve_tax_id_for_delivery`.

**Flussi da verificare esplicitamente:**

1. **Sync PrestaShop → import ordini** — quando si creano righe da ordini PrestaShop, viene usato `id_tax` proveniente da PS o viene risolto tramite `resolve_tax_id_for_delivery`?
2. **Creazione documenti fiscali da ordini** (fatture, DDT) — le righe del documento ereditano `id_tax` dall'ordine o vengono risolte nuovamente?
3. **Aggiornamento righe post-creazione** — se una riga ordine viene modificata manualmente, il `id_tax` viene ricalcolato?

**Procedura:**
```bash
# Trovare tutti i punti dove id_tax viene assegnato su righe/ordini
grep -rn "id_tax" src/ --include="*.py" | grep -v "test" | grep -v "__pycache__"
```

Per ogni occorrenza trovata, verificare che utilizzi `resolve_tax_id_for_delivery` o una sua chiamata a monte.

**Test di integrazione da aggiungere:**
```python
# tests/integration/api/v1/test_vies_tax_resolution_wiring.py
async def test_order_eligible_gets_reverse_charge_on_all_lines():
    """Un ordine con vies_status=eligible deve avere id_tax=reverse_charge su tutte le righe,
    incluse quelle create da sync PS e da documenti derivati."""
    ...
```

---

### TASK BE-2 — Errore strutturato su delete Tax con FK attive 🔴 BLOCCANTE

**Obiettivo:** quando si tenta di eliminare una Tax usata in ordini, documenti o come `reverse_charge_id_tax`, restituire un errore strutturato (non HTTP 500) che il FE può interpretare.

**Implementazione in `TaxService`:**

```python
# src/services/routers/tax_service.py

async def delete_tax(self, id_tax: int) -> None:
    usages = await self.tax_repo.find_usages(id_tax)
    if usages.has_any():
        raise BusinessRuleException(
            code="TAX_IN_USE",
            detail={
                "orders": usages.order_count,
                "documents": usages.document_count,
                "is_reverse_charge": usages.is_reverse_charge,
            }
        )
    await self.tax_repo.delete(id_tax)
```

**Implementazione in `TaxRepository`:**

```python
# src/repositories/tax_repository.py

async def find_usages(self, id_tax: int) -> TaxUsages:
    order_count = await self.session.scalar(
        select(func.count()).where(OrderLine.id_tax == id_tax)
    )
    document_count = await self.session.scalar(
        select(func.count()).where(DocumentLine.id_tax == id_tax)
    )
    # Verifica anche app_configurations
    rc_config = await self.vies_config.get_reverse_charge_id_tax(self.session)
    return TaxUsages(
        order_count=order_count or 0,
        document_count=document_count or 0,
        is_reverse_charge=(rc_config == id_tax),
    )
```

**Response HTTP attesa:** `422 Unprocessable Entity` con body:
```json
{
  "code": "TAX_IN_USE",
  "detail": { "orders": 12, "documents": 3, "is_reverse_charge": false }
}
```

**Test da aggiungere:**
```python
async def test_delete_tax_in_use_returns_structured_error():
    # creare tax, creare ordine con quella tax, tentare delete → 422 con TAX_IN_USE
```

---

### TASK BE-3 — Verificare invalidazione cache su tutti i write Tax 🟡 IMPORTANTE

**Obiettivo:** garantire che ogni operazione di write su Tax/Settings invalidi la cache `init_data` in modo che il FE riceva dati aggiornati.

**Checklist operazioni da verificare:**

| Operazione | Invalida cache? |
|---|---|
| `PUT .../set-country-default` | ✅ (già fatto) |
| `POST /api/v1/taxes/` (nuova) | verificare |
| `PUT /api/v1/taxes/{id}` (modifica) | verificare |
| `DELETE /api/v1/taxes/{id}` | verificare |
| `PUT /api/v1/settings/` (reverse charge) | verificare |

Per ogni operazione mancante, aggiungere nel service:
```python
await self.cache_service.invalidate_pattern("init_data:*")
```

**Test da aggiungere:** dopo `POST /taxes/` → chiamata a `/init/` restituisce la nuova tax.

---

### TASK BE-4 — Uniformare serializzazione `id_country` come `Optional[int]` 🟡 TECH DEBT

**Problema:** da qualche endpoint `id_country` arriva al FE come stringa invece di int/null, costringendo il FE a una coercion difensiva (`toIdNum()`).

**Obiettivo:** `id_country: Optional[int]` in tutti gli schema Pydantic che espongono Tax.

**File da verificare:**
```
src/schemas/tax.py         # TaxSchema, TaxCreateSchema, TaxUpdateSchema
src/schemas/order.py       # se id_tax o id_country compaiono in response ordini
src/schemas/init_data.py   # schema init con taxes[]
```

Assicurarsi che `model_config = ConfigDict(from_attributes=True)` e che i campi nullable siano `Optional[int] = None` e non `Optional[str]`.

---

### TASK BE-5 — Migration `Tax.percentage` a `DECIMAL(5,2)` 🟡 MEDIO TERMINE

**Problema attuale:** `percentage` è `Integer` → FI (25.5%) → salvato come 25 → fatture errate. Stessa cosa per FR aliquota ridotta 5.5%.

**Migration Alembic:**
```python
# migrations/versions/YYYYMMDD_XXXX_tax_percentage_decimal.py
def upgrade():
    op.alter_column(
        'tax',
        'percentage',
        type_=sa.Numeric(5, 2),
        existing_type=sa.Integer(),
    )
    # I dati esistenti (interi) sono compatibili: 22 → 22.00

def downgrade():
    op.alter_column(
        'tax',
        'percentage',
        type_=sa.Integer(),
        existing_type=sa.Numeric(5, 2),
    )
```

**Aggiornamento modello:**
```python
# src/models/tax.py
percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
```

**Aggiornamento schema Pydantic:**
```python
# src/schemas/tax.py
percentage: Decimal = Field(..., ge=0, le=100)
```

**Attenzione:** il FE mostra `percentage` — coordinare con FE per formattazione (es. `25.50` vs `25.5` vs `25`). Backward-compat: i valori interi esistenti restano leggibili.

⚠️ **Eseguire questo task solo dopo avere allineato FE** — cambio tipo in risposta API è breaking.

---

### TASK BE-6 — Verifica idempotenza seed EU in CI 🟢 MINORE

**File:** `src/vies/eu_vat_seed.py` → `setup_eu_country_taxes()`

**Obiettivo:** il seed deve essere sicuro se chiamato due volte nello stesso ambiente CI (es. test paralleli, pipeline rieseguita).

**Verifica:**
```python
# Il seed deve usare INSERT ... ON DUPLICATE KEY UPDATE o equivalente,
# oppure SELECT-before-INSERT con gestione conflict.
async def setup_eu_country_taxes(session: AsyncSession) -> None:
    for iso, rate in EU_VAT_STANDARD_RATES.items():
        existing = await session.scalar(
            select(Tax).where(Tax.name.ilike(f"IVA standard {iso}%"))
        )
        if existing:
            continue  # idempotente
        session.add(Tax(...))
    await session.commit()
```

**Test già esistente:** `tests/scripts/test_setup_initial_eu_taxes.py` — verificare che copra il caso di doppia esecuzione.

---

## Comandi utili

```bash
# Test specifici VIES/Tax
pytest tests/unit/vies/ tests/integration/api/v1/test_tax_country_defaults.py -v

# Test completi area Tax
pytest tests/unit/services/test_tax_service.py \
       tests/unit/services/test_tax_global_default.py \
       tests/unit/services/test_settings_reverse_charge.py \
       -v

# Setup senza seed EU
python scripts/setup_initial.py

# Setup con seed EU (solo test/CI)
SEED_EU_VAT_TAXES=1 python scripts/setup_initial.py

# Migration
alembic upgrade head

# Server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Regole da rispettare in questa sessione

- Architettura obbligatoria: Router → Service → Repository → Model
- DI via `src/core/container.py` + `container_config.py` — mai istanziare service/repo nei router
- Non introdurre tabella `settings` dedicata — usare `app_configurations`
- Un solo `is_default=1` per scope (paese OPPURE globale) — operazioni sempre atomiche
- Nome tax univoco (case insensitive)
- Permessi tax defaults: modulo `settings`, non `taxes`
- Dopo modifiche: aggiornare `README.md` (requisiti, comandi, log ultime modifiche)
- Non committare senza richiesta esplicita

---

## Ordine di esecuzione suggerito

```
BE-1 (audit wiring) → BE-2 (delete strutturato) → BE-3 (cache invalidation)
→ BE-4 (id_country serializzazione) → BE-5 (DECIMAL, coordinare FE) → BE-6 (seed idempotenza)
```

BE-1 e BE-2 sono fiscalmente e funzionalmente critici. BE-5 richiede coordinamento con il FE prima del deploy.
