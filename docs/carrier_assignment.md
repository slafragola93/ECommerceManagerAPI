# Carrier Assignment - Assegnazione Automatica Corrieri

## Panoramica

Il sistema di assegnazione automatica dei corrieri permette di definire regole che vengono applicate automaticamente durante l'import degli ordini da PrestaShop per assegnare il corriere API più appropriato.

## Struttura della Tabella

La tabella `carrier_assignments` contiene le seguenti colonne:

- `id_carrier_assignment`: ID univoco auto-incrementale
- `id_carrier_api`: ID del corriere API da assegnare (FK con `carriers_api`)
- `postal_codes`: Lista di codici postali separati da virgola (es. "20100,20121,20122")
- `countries`: Lista di ID paesi separati da virgola (es. "1,2,3")
- `origin_carriers`: Lista di ID corrieri di origine separati da virgola (es. "1,2,3")
- `min_weight`: Peso minimo per l'assegnazione (in kg)
- `max_weight`: Peso massimo per l'assegnazione (in kg)

## Come Funziona

Durante l'import degli ordini da PrestaShop, il sistema:

1. Estrae le informazioni dall'ordine:
   - Codice postale dall'indirizzo di consegna
   - ID del paese dall'indirizzo
   - ID del corriere di origine da PrestaShop
   - Peso totale dell'ordine

2. Cerca nella tabella `carrier_assignments` una regola che corrisponde a tutti i criteri:
   - Il codice postale è nella lista `postal_codes` (se specificato)
   - L'ID del paese è nella lista `countries` (se specificato)
   - L'ID del corriere di origine è nella lista `origin_carriers` (se specificato)
   - Il peso è compreso tra `min_weight` e `max_weight` (se specificati)

3. Se trova una regola corrispondente, assegna il `id_carrier_api` specificato
4. Se non trova nessuna regola, usa il corriere API di default (ID: 1)

## API Endpoints

### GET /api/v1/carrier_assignments/
Recupera tutte le assegnazioni con filtri opzionali.

**Parametri:**
- `carrier_assignments_ids`: ID delle assegnazioni, separati da virgola
- `carrier_apis_ids`: ID dei carrier API, separati da virgola
- `page`: Pagina corrente (default: 1)
- `limit`: Numero di record per pagina (default: 10)

### GET /api/v1/carrier_assignments/{assignment_id}
Recupera un'assegnazione specifica per ID.

### POST /api/v1/carrier_assignments/
Crea una nuova assegnazione.

**Body:**
```json
{
  "id_carrier_api": 1,
  "postal_codes": "20100,20121,20122",
  "countries": "1",
  "origin_carriers": "1,2",
  "min_weight": 0.0,
  "max_weight": 5.0
}
```

### PUT /api/v1/carrier_assignments/{assignment_id}
Aggiorna un'assegnazione esistente (aggiornamento parziale).

### DELETE /api/v1/carrier_assignments/{assignment_id}
Elimina un'assegnazione.

### POST /api/v1/carrier_assignments/find-match
Trova l'assegnazione che corrisponde ai criteri specificati.

**Parametri:**
- `postal_code`: Codice postale
- `country_id`: ID del paese
- `origin_carrier_id`: ID del corriere di origine
- `weight`: Peso del pacco

## Esempi di Utilizzo

### Esempio 1: Assegnazione per Codice Postale
```json
{
  "id_carrier_api": 1,
  "postal_codes": "20100,20121,20122,20123,20124,20125,20126,20127,20128,20129,20131,20132,20133,20134,20135,20136,20137,20138,20139,20141,20142,20143,20144,20145,20146,20147,20148,20149,20151,20152,20153,20154,20155,20156,20157,20158,20159,20161,20162,20163,20164,20165,20166,20167,20168,20169,20171,20172,20173,20174,20175,20176,20177,20178,20179,20181,20182,20183,20184,20185,20186,20187,20188,20189,20191,20192,20193,20194,20195,20196,20197,20198,20199",
  "countries": "1",
  "min_weight": 0.0,
  "max_weight": 5.0
}
```

### Esempio 2: Assegnazione per Peso
```json
{
  "id_carrier_api": 2,
  "countries": "1",
  "min_weight": 5.1,
  "max_weight": 30.0
}
```

### Esempio 3: Assegnazione per Corriere di Origine
```json
{
  "id_carrier_api": 3,
  "origin_carriers": "1,2,3",
  "min_weight": 0.0,
  "max_weight": 999.0
}
```

## Regole di Priorità

1. Le regole vengono valutate in ordine di ID crescente
2. La prima regola che corrisponde a tutti i criteri viene applicata
3. I campi `NULL` vengono considerati come "qualsiasi valore"
4. Se nessuna regola corrisponde, viene usato il corriere API di default (ID: 1)

## Performance

- La tabella è indicizzata per ottimizzare le ricerche
- Le ricerche vengono eseguite solo durante l'import degli ordini
- Il sistema è progettato per gestire migliaia di regole senza impatti significativi sulle performance

## Logging

Durante l'import degli ordini, il sistema logga:
- I criteri utilizzati per la ricerca
- L'assegnazione trovata (se presente)
- L'uso del corriere di default (se nessuna regola corrisponde)
- Eventuali errori durante il processo di assegnazione

## Migrazione

Per creare la tabella nel database, eseguire il file SQL:
```sql
-- Eseguire il file migrations/create_carrier_assignments_table.sql
```

## Note Tecniche

- I codici postali vengono validati per essere numerici e di lunghezza appropriata
- Gli ID dei paesi e corrieri vengono validati per essere numerici
- Il peso massimo deve essere maggiore o uguale al peso minimo
- Tutti i campi tranne `id_carrier_api` sono opzionali
