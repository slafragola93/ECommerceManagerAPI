# API Reference: Sync Product Images

## Endpoint

**POST** `/api/v1/sync/sync-images`

Sincronizza le immagini dei prodotti per uno store senza eseguire una sync prodotti completa. Utilizza il service e-commerce associato allo store (es. PrestaShop) per recuperare i dati immagine dall’API e riusa la logica esistente di download (prodotti con immagine, prodotti senza immagine/fallback).

### Autenticazione e autorizzazione

- Richiesta autenticazione: sì
- Ruoli ammessi: `ADMIN`
- Permessi richiesti: `C` (Create)

### Parametri

| Parametro  | Posizione | Tipo | Obbligatorio | Descrizione                          |
|-----------|-----------|------|--------------|--------------------------------------|
| `id_store`| Query     | int  | Sì           | ID dello store per cui sincronizzare le immagini |

### Esempio richiesta

```http
POST /api/v1/sync/sync-images?id_store=1
Authorization: Bearer <token>
```

### Risposta

**200 OK**

| Campo                | Tipo   | Descrizione                                      |
|----------------------|--------|--------------------------------------------------|
| `id_store`           | int    | ID dello store processato                        |
| `success`            | bool   | Esito (sempre `true` in caso di 200)             |
| `products_processed` | int    | Numero di prodotti per cui è stata eseguita la sync immagini |
| `message`            | string | Messaggio di riepilogo                           |

Esempio:

```json
{
  "id_store": 1,
  "success": true,
  "products_processed": 150,
  "message": "Image sync completed for 150 products."
}
```

### Errori

| Status | Descrizione |
|--------|-------------|
| 400    | Store non trovato, piattaforma non associata o non supportata (es. solo PrestaShop supportato) |
| 404    | Store con `id_store` non trovato |
| 401    | Non autenticato |
| 403    | Ruolo/permessi insufficienti |

### Flusso

1. Validazione store (esistenza e piattaforma).
2. Creazione del service e-commerce tramite `create_ecommerce_service(store_id, db)`.
3. Caricamento prodotti dello store con `id_origin` non nullo dal database.
4. Fetch dall’API della piattaforma (batch) per `id_default_image` e `name`.
5. Esecuzione della logica di download/aggiornamento immagini (e fallback per prodotti senza immagine).
6. Warm-up della cache immagini (se applicabile).
7. Restituzione del riepilogo.

### Note

- L’endpoint può essere chiamato in qualsiasi momento; non dipende da una precedente sync prodotti.
- Sono processati tutti i prodotti dello store con `id_origin` valorizzato (sia con che senza immagine già presente).
