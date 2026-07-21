# BE — Reso solo spedizione

Contratto richiesto dal frontend per abilitare la creazione di un reso con **sola spedizione** (nessuna riga prodotto selezionata).

## Endpoint

`POST /api/v1/orders/{id_order}/returns`

## Payload

```json
{
  "order_details": [],
  "includes_shipping": true,
  "note": "opzionale"
}
```

## Regole di validazione

| Caso | Esito atteso |
|------|--------------|
| `includes_shipping=true` + `order_details=[]` | **201** — crea reso dell'importo spedizione ordine |
| `includes_shipping=true` + `order_details` con prodotti | **201** — prodotti + spedizione (già supportato) |
| `includes_shipping=false` + `order_details=[]` | **4xx** — almeno una riga prodotto o shipping |
| `includes_shipping=true` ma ordine senza costo spedizione | **4xx** — messaggio chiaro |

## Persistenza / GET dettaglio

Dopo la creazione, `GET /api/v1/orders/returns/get-return-by-id/{id}` (e liste correlate) deve esporre:

1. `includes_shipping: true`
2. Totali documento coerenti con l'importo spedizione resa
3. Una riga in `details[]` riconoscibile come spedizione:
   - preferito: `"is_shipping": true`, `product_name: "Spedizione"`
   - fallback accettato dal FE: `id_order_detail: 0` + nome contenente "spedizion"/"shipping"

Esempio riga:

```json
{
  "id_fiscal_document_detail": 123,
  "id_fiscal_document": 45,
  "id_order_detail": 0,
  "is_shipping": true,
  "product_name": "Spedizione",
  "product_reference": "SHIPPING",
  "product_qty": 1,
  "unit_price_net": 8.2,
  "unit_price_with_tax": 10,
  "total_price_net": 8.2,
  "total_price_with_tax": 10,
  "id_tax": 22
}
```

## Note FE

Il frontend già:
- abilita il submit del modale reso con solo toggle spedizione;
- invia `order_details: []` + `includes_shipping: true`;
- mappa/visualizza la riga `Spedizione` in tabella dettaglio reso;
- in assenza temporanea della riga nei `details`, sintetizza una riga UI dai totali shipping (fallback).
