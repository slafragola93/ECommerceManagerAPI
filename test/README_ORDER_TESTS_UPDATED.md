# Test per gli Endpoint Order - Aggiornati

## Panoramica

I test per gli endpoint Order sono stati aggiornati per riflettere le modifiche apportate a `OrderUpdateSchema`. Ora tutti i campi di relazione utilizzano i nomi dei campi del database (con prefisso `id_`).

## Modifiche Apportate

### 1. OrderUpdateSchema
- **Prima**: `address_delivery`, `address_invoice`, `customer`, `shipping`, `sectional`
- **Dopo**: `id_address_delivery`, `id_address_invoice`, `id_customer`, `id_shipping`, `id_sectional`

### 2. Test Aggiornati
- `test/routers/test_order.py` - Test base aggiornati
- `test/routers/test_order_advanced.py` - Test avanzati aggiornati
- `test/routers/test_order_update_schema.py` - **NUOVO** - Test specifici per OrderUpdateSchema

## File di Test

### test_order.py
Test base per tutti gli endpoint Order:
- GET /orders/ (con filtri e paginazione)
- GET /orders/{id}
- POST /orders/
- PUT /orders/{id}
- DELETE /orders/{id}
- PATCH /orders/{id}/status
- PATCH /orders/{id}/payment
- GET /orders/{id}/details
- GET /orders/{id}/summary

### test_order_advanced.py
Test avanzati per scenari complessi:
- Filtri combinati
- Workflow CRUD completo
- Aggiornamenti di stato e pagamento
- Integrazione con dettagli ordine
- Casi limite e gestione errori

### test_order_update_schema.py
Test specifici per OrderUpdateSchema:
- Validazione schema con nuovi nomi campi
- Aggiornamenti parziali
- Compatibilità con vecchi nomi (dovrebbe fallire)
- Test con tipi di dati diversi
- Test con valori null e negativi

## Come Eseguire i Test

### Eseguire tutti i test Order
```bash
pytest test/routers/test_order*.py -v
```

### Eseguire test specifici
```bash
# Solo test base
pytest test/routers/test_order.py -v

# Solo test avanzati
pytest test/routers/test_order_advanced.py -v

# Solo test per OrderUpdateSchema
pytest test/routers/test_order_update_schema.py -v
```

### Eseguire un singolo test
```bash
pytest test/routers/test_order.py::TestOrderEndpoints::test_update_order_success -v
```

## Test di Aggiornamento Parziale

I nuovi test verificano che gli aggiornamenti parziali funzionino correttamente:

### Esempio 1: Aggiornamento singolo campo
```json
PUT /api/v1/orders/1
{
  "total_price": 199.99
}
```

### Esempio 2: Aggiornamento campi di relazione
```json
PUT /api/v1/orders/1
{
  "id_address_delivery": 2,
  "id_address_invoice": 2
}
```

### Esempio 3: Aggiornamento misto
```json
PUT /api/v1/orders/1
{
  "id_customer": 2,
  "is_payed": true,
  "total_weight": 3.0
}
```

## Validazione Schema

I test verificano che:
- ✅ I nuovi nomi dei campi siano accettati
- ❌ I vecchi nomi dei campi siano rifiutati
- ✅ I campi opzionali funzionino correttamente
- ✅ I tipi di dati siano validati
- ✅ I valori null siano gestiti

## Fixture Utilizzate

I test utilizzano le seguenti fixture da `test/utils.py`:
- `test_order` - Singolo ordine di test
- `test_orders` - Multipli ordini di test
- `test_customer` - Cliente di test
- `test_address` - Indirizzo di test
- `test_order_state` - Stato ordine di test
- `test_platform` - Piattaforma di test
- `test_payment` - Metodo di pagamento di test
- `test_shipping` - Spedizione di test
- `test_sectional` - Sezionale di test

## Copertura Test

I test coprono:
- ✅ Tutti gli endpoint CRUD
- ✅ Aggiornamenti parziali
- ✅ Validazione dati
- ✅ Gestione errori
- ✅ Autorizzazione
- ✅ Filtri e paginazione
- ✅ Casi limite
- ✅ Compatibilità schema

## Note Importanti

1. **Nomi Campi**: Tutti i test ora utilizzano i nomi dei campi del database
2. **Aggiornamenti Parziali**: Il metodo `update` ora supporta aggiornamenti parziali
3. **Validazione**: I vecchi nomi dei campi non sono più accettati
4. **Compatibilità**: I test verificano che la migrazione sia completa

## Risoluzione Problemi

### Test che falliscono
1. Verificare che i nomi dei campi siano corretti
2. Controllare che le fixture siano disponibili
3. Verificare che il database di test sia pulito

### Errori di validazione
1. Controllare che `OrderUpdateSchema` sia importato correttamente
2. Verificare che i tipi di dati siano corretti
3. Controllare che i valori null siano gestiti

### Errori di autorizzazione
1. Verificare che `override_get_current_user` sia configurato
2. Controllare che i permessi siano corretti
3. Verificare che l'utente di test abbia i ruoli necessari
