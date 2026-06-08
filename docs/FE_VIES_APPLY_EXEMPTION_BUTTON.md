# FE — Pulsante «Applica esenzione VIES» (KO → OK)

Guida per il gestionale Angular (repo FE separato). Il backend **ECommerceManagerAPI** espone già l’endpoint; non serve nuova API.

**Prompt da incollare in chat FE (Cursor/Claude):** [.cursor/tasks_claude/prompt_FE_vies_apply_exemption.md](../.cursor/tasks_claude/prompt_FE_vies_apply_exemption.md)

---

## Comportamento prodotto

| Prima | Dopo click |
|-------|------------|
| `vies_status`: `not_eligible` o `null` | `eligible` |
| Righe ordine con IVA (es. 22%) | `id_tax` = aliquota VIES (`reverse_charge_id_tax` da Impostazioni, altrimenti prima tax 0%) |
| Totali **ivati** riga | **Invariati** (ricalcolo solo imponibile) |

**Non** usare `PUT /orders/{id}` con solo `vies_status: eligible` — non ricalcola le righe. Usare l’endpoint dedicato.

---

## API

### Singolo ordine

```http
PATCH /api/v1/orders/{id_order}/apply-vies-exemption
Authorization: Bearer <token>
```

- **Permesso RBAC:** `orders` + azione `update`
- **Body:** nessuno
- **200:**

```json
{
  "status": "success",
  "data": {
    "id_order": 123,
    "vies_status": "eligible",
    "total_price_with_tax": 122.0,
    "order_details": [ ... ]
  }
}
```

- **404:** ordine inesistente  
- **401/403:** auth / permessi (gestiti dall’`ErrorInterceptor` esistente)

### Bulk (lista ordini)

```http
POST /api/v1/orders/bulk-apply-vies-exemption
Content-Type: application/json

{ "order_ids": [1, 2, 3] }
```

Transazione atomica: se un id non esiste → errore e rollback di tutto il batch.

---

## Quando mostrare il pulsante

```typescript
type ViesStatus = 'eligible' | 'not_eligible' | null;

function canApplyViesExemption(order: { vies_status?: ViesStatus }): boolean {
  return order.vies_status !== 'eligible';
}
```

Suggerimenti UX:

- Etichetta: **«Applica esenzione VIES»** o **«Conferma VIES OK»**
- Tooltip: conversione manuale dopo verifica operatore; totali ivati invariati.
- **Conferma** prima della chiamata (Swal / dialog).
- Disabilitare durante la richiesta (`loading`).
- Dopo successo: aggiornare dettaglio ordine e righe dallo `data` della response (o refetch `GET /orders/{id}`).

Non mostrare se l’utente non ha `orders.update`.

---

## Implementazione Angular (schema consigliato)

### 1) Service HTTP

```typescript
// orders-api.service.ts (o order.service.ts)
applyViesExemption(orderId: number): Observable<OrderApiResponse> {
  return this.http.patch<OrderApiResponse>(
    `${this.baseUrl}/api/v1/orders/${orderId}/apply-vies-exemption`,
    null
  );
}

bulkApplyViesExemption(orderIds: number[]): Observable<{ status: string; data: unknown }> {
  return this.http.post(
    `${this.baseUrl}/api/v1/orders/bulk-apply-vies-exemption`,
    { order_ids: orderIds }
  );
}
```

Adatta `OrderApiResponse` al tipo già usato per `GET /orders/{id}` (`data.vies_status` stringa `"eligible"`).

### 2) NgRx (se il modulo ordini usa store)

```typescript
// orders.actions.ts
export const applyViesExemption = createAction(
  '[Orders] Apply VIES Exemption',
  props<{ orderId: number }>()
);
export const applyViesExemptionSuccess = createAction(
  '[Orders] Apply VIES Exemption Success',
  props<{ order: Order }>()
);
export const applyViesExemptionFailure = createAction(
  '[Orders] Apply VIES Exemption Failure',
  props<{ error: unknown }>()
);
```

```typescript
// orders.effects.ts
applyViesExemption$ = createEffect(() =>
  this.actions$.pipe(
    ofType(applyViesExemption),
    switchMap(({ orderId }) =>
      this.ordersApi.applyViesExemption(orderId).pipe(
        map((res) => applyViesExemptionSuccess({ order: res.data })),
        catchError((error) => of(applyViesExemptionFailure({ error })))
      )
    )
  )
);

// Success: aggiornare entità in store + Swal QUI (non toast ottimista nel service)
applyViesExemptionSuccess$ = createEffect(
  () =>
    this.actions$.pipe(
      ofType(applyViesExemptionSuccess),
      tap(() => this.alertService.success('Esenzione VIES applicata', '...'))
    ),
  { dispatch: false }
);
```

**Importante (cfr. backlog FE-4):** non mostrare successo prima della risposta HTTP.

### 3) Componente dettaglio ordine

```html
<button
  *ngIf="canApplyViesExemption(order)"
  mat-raised-button
  color="primary"
  [disabled]="applyingVies"
  (click)="onApplyViesExemption()"
>
  Applica esenzione VIES
</button>
```

```typescript
onApplyViesExemption(): void {
  this.confirmService
    .confirm({
      title: 'Conferma VIES',
      text: 'Impostare l\'ordine come VIES OK (0% IVA sulle righe)? I totali ivati restano invariati.',
    })
    .pipe(
      filter(Boolean),
      tap(() => (this.applyingVies = true)),
      switchMap(() =>
        this.store.dispatch(
          applyViesExemption({ orderId: this.order.id_order })
        )
        // oppure chiamata diretta al service + subscribe
      ),
      finalize(() => (this.applyingVies = false))
    )
    .subscribe();
}
```

### 4) Lista ordini (opzionale)

- Azione riga / bulk con selezione multipla → `bulkApplyViesExemption(selectedIds)`.
- Filtro lista: `GET /api/v1/orders/?vies_status=not_eligible` per trovare candidati KO.

---

## Badge / stato in UI

| `vies_status` | Label suggerita |
|---------------|-----------------|
| `eligible` | VIES OK |
| `not_eligible` | VIES KO |
| `null` / assente | VIES N/D |

Dopo il pulsante, il badge deve passare a **VIES OK** senza reload completo della pagina se aggiorni lo store dalla response.

---

## Prerequisiti backend (già in prod/dev)

- `reverse_charge_id_tax` configurato in **Impostazioni VIES** (`GET/PUT /api/v1/settings/`) — altrimenti il BE usa la prima aliquota 0% disponibile.
- Server riavviato dopo deploy BE-ALIQ-01M.

---

## Test manuale

1. Ordine con `vies_status: not_eligible` e riga a 22%.
2. Click pulsante → conferma.
3. `PATCH apply-vies-exemption` → 200, `vies_status: eligible`.
4. Riga: `id_tax` = aliquota 0% / reverse charge; `total_price_with_tax` uguale a prima.

Swagger: http://localhost:8000/docs → sezione **Order** → `apply_vies_exemption`.

---

## Checklist implementazione FE

- [ ] Metodo HTTP `applyViesExemption(id)`
- [ ] Permesso `orders.update` sul pulsante (`*hasPermission`)
- [ ] Visibilità solo se `vies_status !== 'eligible'`
- [ ] Dialog di conferma
- [ ] Success solo dopo risposta 200 (no toast ottimista)
- [ ] Aggiornamento modello ordine + righe in UI
- [ ] (Opzionale) Bulk su griglia ordini
