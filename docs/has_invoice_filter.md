# Task: Aggiunta filtro e flag `has_invoice` sulla lista ordini

## Obiettivo

Esporre nella lista ordini un flag calcolato `has_invoice: bool` e permettere il filtro lato backend degli ordini fatturati / non fatturati, **senza modificare il database** e **senza duplicare lo stato**.

Un ordine è considerato fatturato se esiste almeno un `FiscalDocument` con:
- `FiscalDocument.id_order == Order.id_order`
- `FiscalDocument.document_type == "invoice"`

`credit_note` e `return` sono esplicitamente fuori scope di questo task.

---

## Endpoint coinvolto

`GET /api/v1/orders`

Nuovo query param:
- `has_invoice: Optional[bool] = None`
  - `true` → solo ordini gia fatturati
  - `false` → solo ordini non fatturati
  - assente → nessun filtro

Nuovo campo in response (per ogni ordine della lista):
- `has_invoice: bool`

Esempi:
- `GET /api/v1/orders` — tutti, con `has_invoice` calcolato per ciascun ordine
- `GET /api/v1/orders?has_invoice=true&page=1&limit=20`
- `GET /api/v1/orders?has_invoice=false&is_payed=true&date_from=2025-01-01`

---

## File modificati

### 1. `src/schemas/order_schema.py`
Aggiunto `has_invoice: bool = False` ai seguenti schemi di response:
- `OrderSimpleResponseSchema` (usato nella lista ordini)
- `OrderResponseSchema`
- `OrderIdSchema` (usato dal `GET /api/v1/orders/{order_id}`)

### 2. `src/repository/interfaces/order_repository_interface.py`
Aggiunto parametro `has_invoice: Optional[bool] = None` alle firme di:
- `IOrderRepository.get_all(...)`
- `IOrderRepository.get_count(...)`

### 3. `src/repository/order_repository.py`
- Import aggiunto: `from ..models.fiscal_document import FiscalDocument`
- `get_all(...)`:
  - Nuovo parametro `has_invoice: Optional[bool] = None`
  - Filtro tramite **EXISTS subquery correlata** su `FiscalDocument(id_order == Order.id_order, document_type == 'invoice')`
  - Dopo la fetch, **batch-precompute** degli `id_order` fatturati per la pagina corrente, con assegnazione di `o._has_invoice` come attributo di istanza (no N+1)
- `get_count(...)`:
  - Nuovo parametro `has_invoice: Optional[bool] = None`
  - Stesso filtro EXISTS, in modo che `total` resti coerente con la lista paginata
- `formatted_output(...)`:
  - Aggiunto `"has_invoice": self._resolve_has_invoice(order)` nella response base
- Nuovo helper privato `_resolve_has_invoice(order)`:
  - Usa il valore precalcolato (`order._has_invoice`) se presente
  - Altrimenti esegue una EXISTS query mirata (fallback per `get_by_id` e usi singoli)

### 4. `src/routers/order.py`
- Aggiunto query param:
  ```python
  has_invoice: Optional[bool] = Query(
      None,
      description="Filtro per ordini gia fatturati (true) o non fatturati (false). "
                  "Derivato da FiscalDocument(document_type=invoice)"
  )
  ```
- Propagato a `or_repo.get_all(...)` e `or_repo.get_count(...)`

---

## Approccio e razionale

- **Dato derivato, non persistito**: nessuna nuova colonna su `orders` o `fiscal_documents`, nessuna migrazione Alembic.
- **Filtro lato backend**: applicato in SQL tramite `EXISTS` correlato; identico in `get_all` e `get_count`, quindi paginazione e `total` restano consistenti.
- **Niente N+1 sul flag**: in `get_all` viene eseguita **una sola** query batch sugli `id_order` della pagina corrente per determinare quali sono fatturati. `formatted_output` legge il risultato precalcolato.
- **Fallback per uso singolo**: `_resolve_has_invoice` fa una EXISTS mirata se il flag non e' stato precalcolato (ad es. su `GET /api/v1/orders/{id}`), mantenendo il dato sempre coerente.
- **Solo `invoice`**: `credit_note` e `return` non concorrono al flag, come da requisito.
- **Pattern architetturale**: il listing nel codebase attuale chiama il repository direttamente dal router (pattern preesistente). Il parametro e' stato aggiunto rispettando l'interfaccia (`IOrderRepository`) per coerenza con ISP. Non e' stato introdotto un nuovo metodo di listing su `OrderService` per non fare refactor fuori scope.

---

## Vincoli rispettati

- [x] Nessuna modifica al database
- [x] Nessuna nuova colonna su `orders` o `fiscal_documents`
- [x] Nessuna migrazione Alembic
- [x] Nessuna business logic nel router
- [x] Nessuna query SQLAlchemy nel router
- [x] Stato non duplicato nel DB: `has_invoice` derivato a runtime
- [x] Interfaccia `IOrderRepository` aggiornata
- [x] FastAPI + SQLAlchemy 2.0 + Pydantic v2 mantenuti
- [x] Solo `document_type == "invoice"` (no `credit_note`, no `return`)
- [x] Nessuna logica frontend introdotta
- [x] Nessuna nuova API separata

---

## Punti da verificare manualmente

1. La response del router e' un `dict` (no `response_model`), quindi `has_invoice` e' gia propagato; gli schemi sono aggiornati per documentazione/typing/OpenAPI.
2. Verificare in Swagger/OpenAPI che il parametro `has_invoice` appaia con tipo booleano corretto.
3. Su volumi alti, monitorare il piano d'esecuzione di `EXISTS` su `fiscal_documents`: gli indici esistenti (`id_order`, `document_type`) dovrebbero essere sufficienti.
4. Il batch query in `get_all` aggiunge una sola SELECT sulla pagina corrente (al massimo `limit` ordini): impatto trascurabile.
5. Se in futuro il listing verra spostato dietro `OrderService`, il parametro `has_invoice` e' gia pronto da propagare al nuovo metodo del service.

---

## Test minimi consigliati

- `GET /api/v1/orders` su dataset con ordini misti → response contiene `has_invoice` per ciascun ordine, coerente con `fiscal_documents`.
- `GET /api/v1/orders?has_invoice=true` → solo ordini con almeno un `FiscalDocument(document_type='invoice')`; `total` corrisponde al numero filtrato.
- `GET /api/v1/orders?has_invoice=false` → solo ordini privi di fatture (anche se hanno `credit_note` o `return`, devono essere considerati "non fatturati").
- Paginazione con filtro: `?has_invoice=true&page=2&limit=10` → coerenza tra `len(orders)`, `page`, `limit`, `total`.
- Combinazione filtri: `?has_invoice=true&is_payed=true&date_from=2025-01-01` → AND su tutte le condizioni.
- Ordine con fattura **e** nota di credito → `has_invoice=true`. Ordine con sola `credit_note` → `has_invoice=false`.
- `GET /api/v1/orders/{id}` → `has_invoice` valorizzato correttamente anche sulla risorsa singola (path del fallback EXISTS).

---

## Verifiche eseguite

- [x] Sintassi Python valida (`ast.parse`) sui 4 file modificati
- [x] Nessun errore del linter sui file modificati
