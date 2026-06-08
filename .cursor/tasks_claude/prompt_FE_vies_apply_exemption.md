# Prompt sessione FE — Pulsante «Applica esenzione VIES» (KO → OK)

Copia tutto il contenuto sotto la riga `---` e incollalo in una nuova chat Cursor/Claude sul **repository del gestionale Angular**.

---

## Contesto

Il backend **ECommerceManagerAPI** (FastAPI) espone già l’azione per convertire manualmente un ordine da **VIES KO** a **VIES OK** dopo verifica operatore.

**Regola prodotto (vincolante):**

- Gli ordini da **sync PrestaShop** non vanno “corretti” cambiando solo un campo: i prezzi/aliquote restano quelli importati.
- La conversione VIES è un’**azione esplicita** dell’operatore (pulsante), non un salvataggio generico del form ordine.
- **Non** usare `PUT /api/v1/orders/{id}` con `{ "vies_status": "eligible" }` — aggiorna solo il flag, **non** ricalcola le righe a 0% né mantiene i totali ivati in modo coerente.

---

## Obiettivo task FE

Implementare nel gestionale:

1. **Pulsante** in dettaglio ordine (e opzionale bulk in lista): «Applica esenzione VIES» / «Conferma VIES OK».
2. Chiamata a **`PATCH /api/v1/orders/{id}/apply-vies-exemption`** dopo conferma utente.
3. Aggiornamento UI (badge VIES, righe, totali) dalla response o refetch.
4. RBAC, loading, messaggi successo/errore **solo dopo** risposta HTTP (no toast ottimista — cfr. backlog FE-4).

---

## API Backend (già deployabile)

### Singolo ordine (obbligatorio per questo task)

```http
PATCH /api/v1/orders/{id_order}/apply-vies-exemption
Authorization: Bearer <JWT>
Content-Type: application/json
```

- **Body:** nessuno (`null` o `{}`)
- **Permesso:** modulo `orders`, azione `update` (`orders.update`)
- **200 OK:**

```json
{
  "status": "success",
  "data": {
    "id_order": 123,
    "vies_status": "eligible",
    "total_price_with_tax": 122.0,
    "total_price_net": 100.0,
    "order_details": [
      {
        "id_order_detail": 1,
        "id_tax": 5,
        "unit_price_with_tax": 122.0,
        "unit_price_net": 122.0,
        "total_price_with_tax": 122.0,
        "total_price_net": 122.0
      }
    ]
  }
}
```

**Effetto lato server:**

- Tutte le righe ordine (non legate a documento) → `id_tax` = aliquota VIES (`reverse_charge_id_tax` da Impostazioni, altrimenti prima tax 0%).
- **Totali ivati riga invariati**; ricalcolo solo imponibile (netto = ivato a 0%).
- `vies_status` → `"eligible"`.
- Evento audit `ORDER_VIES_EXEMPTION_APPLIED` (solo BE).

**Errori:**

| Status | Caso |
|--------|------|
| 404 | Ordine inesistente |
| 401 / 403 | Token / permesso `orders.update` |
| 422 / 400 | Validazione (raro su questo endpoint) |

### Bulk (opzionale — fase 2)

```http
POST /api/v1/orders/bulk-apply-vies-exemption
{ "order_ids": [1, 2, 3] }
```

- Stesso permesso `orders.update`.
- Transazione **atomica**: un id mancante → errore, nessun ordine aggiornato.
- **200:** `{ "status": "success", "data": { "processed": 3, ... } }` (verificare forma esatta in Swagger).

### Filtro lista (supporto UX)

```http
GET /api/v1/orders/?vies_status=not_eligible&page=1&limit=50
```

Valori: `eligible` | `not_eligible` | `null` (solo ordini senza stato).

### Cosa NON fare

```http
PUT /api/v1/orders/123
{ "vies_status": "eligible" }
```

→ **Sbagliato** per questo caso d’uso: non applica esenzione sulle righe.

---

## Modello dati FE

```typescript
type ViesStatus = 'eligible' | 'not_eligible' | null | undefined;

interface Order {
  id_order: number;
  vies_status?: ViesStatus;
  order_details?: OrderDetail[];
  total_price_with_tax?: number;
  total_price_net?: number;
  // ... altri campi già presenti nel progetto
}
```

**Visibilità pulsante:**

```typescript
export function canApplyViesExemption(order: Pick<Order, 'vies_status'>): boolean {
  return order.vies_status !== 'eligible';
}
```

Mostrare per `not_eligible` e `null`/`undefined` (VIES N/D o KO).

**Badge suggeriti:**

| `vies_status` | UI |
|---------------|-----|
| `eligible` | VIES OK (verde) — nascondi pulsante |
| `not_eligible` | VIES KO (rosso/arancio) — mostra pulsante |
| `null` | VIES N/D (grigio) — mostra pulsante |

---

## Implementazione richiesta

### 1. Service HTTP

Aggiungere al service ordini esistente (stesso `baseUrl` e interceptor JWT degli altri endpoint ordini):

```typescript
applyViesExemption(orderId: number): Observable<ApiResponse<Order>> {
  return this.http.patch<ApiResponse<Order>>(
    `${environment.apiUrl}/api/v1/orders/${orderId}/apply-vies-exemption`,
    null
  );
}
```

Tipo `ApiResponse<T>` = `{ status: 'success'; data: T }` se già usato nel progetto.

### 2. Dettaglio ordine — UI

- Posizione: toolbar/header dettaglio ordine (vicino badge stato ordine o sezione fiscale).
- `*ngIf="canApplyViesExemption(order)"` + `*hasPermission="'orders'; action: 'update'"` (adatta alla direttiva permessi del progetto).
- Click → **dialog conferma** (Swal o `ConfirmService` esistente):

  > «Confermi l’esenzione VIES? Le righe passeranno a 0% IVA; i totali con IVA restano invariati.»

- Durante request: `[disabled]="applyingVies"` + spinner.
- **Success:** aggiornare `order` dallo `response.data` **oppure** `GET /api/v1/orders/{id}?show_details=true` (se il PATCH non restituisce tutti i campi che la UI usa).
- **Error:** lasciare gestione a `ErrorInterceptor` + eventuale messaggio locale.

### 3. NgRx (se il modulo ordini usa store)

- Action: `applyViesExemption({ orderId })`
- Effect: chiama service, `map` → `applyViesExemptionSuccess({ order: res.data })`
- Reducer: sostituire entità ordine in store (e righe collegate).
- **Toast success nell’effect `Success$`**, non nel componente prima della chiamata.

### 4. Lista ordini (opzionale)

- Checkbox selezione + azione «Applica VIES» → `bulkApplyViesExemption(ids)`.
- Colonna o chip `vies_status` se non già presente.

---

## Criteri di accettazione (Definition of Done)

- [ ] Pulsante visibile solo se `vies_status !== 'eligible'` e utente ha `orders.update`.
- [ ] Click → conferma → `PATCH apply-vies-exemption` → nessun `PUT` con solo `vies_status`.
- [ ] Dopo 200: badge **VIES OK**; righe con aliquota 0% (o reverse charge); `total_price_with_tax` riga **uguale** a prima dell’azione (verifica su ordine test).
- [ ] Nessun messaggio di successo prima del completamento HTTP.
- [ ] 403/404 gestiti senza stato UI incoerente (ordine non marcato eligible se chiamata fallita).
- [ ] (Opzionale) Bulk e filtro `vies_status=not_eligible` in lista.

---

## Test manuale (con backend locale)

1. Backend: `uvicorn src.main:app --reload` → http://localhost:8000/docs
2. Ordine con `vies_status: "not_eligible"` e almeno una riga con IVA > 0%.
3. PATCH da Swagger o da FE → verificare `eligible` e netti = ivati sulle righe.
4. Ripetere da UI con lo stesso ordine.

**Impostazioni (opzionale):** `GET /api/v1/settings/` → `reverse_charge_id_tax`; se configurato, le righe usano quell’`id_tax`.

---

## Riferimenti backend (solo lettura)

- Router: `src/routers/order.py` — `apply_vies_exemption`, `bulk_apply_vies_exemption`
- Logica: `src/services/routers/order_service.py` — `_apply_vies_exemption_core`
- Guida estesa: `docs/FE_VIES_APPLY_EXEMPTION_BUTTON.md` nel repo **ECommerceManagerAPI**
- Test integrazione: `tests/integration/api/v1/test_order_vies_exemption.py`

---

## Note architettura FE

- Seguire convenzioni esistenti del modulo **orders** (naming service, store, permessi).
- Non duplicare logica fiscale lato FE: il BE calcola netti e `id_tax`.
- Il FE invia solo l’**intento** (click confermato); non inviare array di righe ricalcolate manualmente.

---

## Fuori scope (non implementare in questo task)

- Modifica regole sync PrestaShop.
- Cambio `vies_status` tramite form generico ordine senza endpoint dedicato.
- Tab impostazioni IVA / `reverse_charge_id_tax` (task FE-VIES settings separato se previsto).
- Creazione nuovo ordine con `vies_status: eligible` su `POST /orders` (altro flusso).

---

## Ordine di lavoro suggerito

1. Metodo HTTP + tipi response.
2. Pulsante + conferma su dettaglio ordine.
3. Wire store / refresh UI.
4. Test manuale con backend.
5. (Opzionale) Bulk + filtro lista.

Rispondi in italiano. Diff minimi; riusa componenti e pattern già presenti nel codebase FE.
