# Handoff FE → BE — FastLDV sync tracking (creative_light3)

**Data:** 2026-06-11  
**Repo FE:** creative_light3 (Angular gestionale)  
**Repo BE:** ECommerceManagerAPI  
**Stato:** FE implementato ✅ · BE `BE-FASTLDV-EVT` deployato ✅ · **QA congiunto da eseguire**

---

## Contesto

Dopo `POST /api/v1/fastldv/notify-print`, il BE emette `order.tracking.updated` via SSE. Il FE aggiorna lista ordini e modale dettaglio senza F5.

---

## Implementazione FE (completata)

| Componente | File | Note |
|------------|------|------|
| SSE client | `order-events.service.ts` | `fetch` + stream + JWT; reconnect backoff 1s→30s; stop su 401/403 |
| Parser SSE | `order-events-sse.parser.ts` | Parse `event:` + `data:`; ignora `: keepalive` |
| Endpoint | `global-component.ts` | `eventsStream: "/api/v1/events/stream"` |
| Lista ordini | `order-list.component.ts` | SSE on enter / off leave |
| NgRx | `trackingUpdatedFromEvent` + reducer | Patch `items[]` + `selectedOrder` |
| Patch locale | `resolve-tracking-patch-from-event.util.ts` | No GET se payload ha `tracking` |
| Modale | `order-details-modal.component.ts` | Ascolta evento, aggiorna tracking |
| Feature flag | `order-events.config.ts` | `ORDER_EVENTS_SSE_ENABLED`, `ORDER_EVENTS_VISIBILITY_RECONNECT` |
| Test | parser + util specs | 9 test PASS |

---

## Contratto SSE (allineato BE ↔ FE)

```http
GET {API_BASE}/api/v1/events/stream
Authorization: Bearer <JWT>
Accept: text/event-stream
```

```
event: order.tracking.updated
data: {"id_order":48564,"tracking":"BRT123456789","awb":"BRT123456789","source":"fastldv","timestamp":"..."}
```

| Campo | BE v1 | FE |
|-------|-------|-----|
| `id_order` | ✅ sempre (PK gestionale) | Correlazione UI |
| `tracking` | ✅ | Patch colonna spedizione / modale |
| `awb` | ✅ (= `tracking` su notify-print FastLDV) | Patch `shipping.awb` in NgRx |
| `source` | ✅ `fastldv` | Informativo |
| `timestamp` | ✅ ISO UTC | Informativo |

**Identificatori:** il FE usa solo `id_order`. `id_origin` (PS / `0`) non compare negli eventi SSE.

---

## Flusso end-to-end

```
FastLDV → POST notify-print → DB tracking → EventBus → SSE fan-out
  → OrderEventsService (FE)
  → patch NgRx se ordine in lista/modale
  → UI aggiornata (~2s, no F5)
```

- Idempotenza FE: stesso `id_order` + stesso `tracking` → no-op
- Lifecycle: 1 connessione SSE per tab, solo su route `/orders`

---

## QA congiunto (checklist)

| # | Scenario | Esito atteso |
|---|----------|--------------|
| 1 | Lista ordini aperta, ordine senza tracking | Dopo notify-print, tracking visibile entro ~2s senza F5 |
| 2 | Modale dettaglio stesso ordine aperto | Campo tracking aggiornato |
| 3 | DevTools Network | Nessun `GET /orders/{id}` se evento include `tracking` |
| 4 | Utente senza `orders:read` | `403` su stream; FE non loop reconnect |
| 5 | Disconnect/reconnect SSE | Nessun storm di GET |
| 6 | Ordine PS | Body notify con `id_origin` PS; evento SSE con `id_order` interno |

**Curl notify-print (ordine gestionale, `id_origin` = codice scansione = `id_order`):**

```bash
curl -X POST "http://localhost:8000/api/v1/fastldv/notify-print" \
  -H "Content-Type: application/json" \
  -H "X-FastLDV-Key: <FASTLDV_API_KEY>" \
  -d '{"id_origin":69100,"tracking":"BRT123456789","colli":1,"carrier":"BRT","operatore":"test","stampante":"ZDesigner"}'
```

Per ordine PrestaShop: `id_origin` nel body = ID shop (es. `457300`); l'evento SSE avrà `id_order` interno (es. `48564`).

---

## Produzione — proxy nginx

Su `/api/v1/events/stream`:

```nginx
proxy_buffering off;
proxy_read_timeout 3600s;
proxy_http_version 1.1;
```

---

## Fuori scope v1

- App FastLDV PHP (repo separato)
- Epic campanella N2
- `PATCH /fastldv/order/{code}/shipping-params` (BE-FASTLDV-3)

---

## Prossimi step opzionali

| Area | Idea |
|------|------|
| FE | SSE globale sessione (N2), flag da `environment` |
| BE | Includere `awb` in emit se valorizzato su `shipping` |
| Entrambi | Estendere tipi evento oltre `order.tracking.updated` |
| Magazzino | Cutover app FastLDV (Fase 3) — `prompt_FE_fastldv_migration.md` |
