# Test per gli Endpoint Order

## Panoramica

Questo documento descrive i test implementati per gli endpoint Order dell'ECommerceManagerAPI.

## File di Test

### 1. `test_order.py`
Test base per tutti gli endpoint Order:
- **GET /orders/** - Recupero lista ordini con filtri
- **GET /orders/{id}** - Recupero singolo ordine
- **POST /orders/** - Creazione nuovo ordine
- **PUT /orders/{id}** - Aggiornamento ordine
- **DELETE /orders/{id}** - Eliminazione ordine
- **PATCH /orders/{id}/status** - Aggiornamento stato ordine
- **PATCH /orders/{id}/payment** - Aggiornamento pagamento
- **GET /orders/{id}/details** - Recupero dettagli ordine
- **GET /orders/{id}/summary** - Recupero riassunto ordine

### 2. `test_order_advanced.py`
Test avanzati per scenari complessi:
- Filtri combinati
- Workflow CRUD completi
- Gestione errori
- Casi limite
- Performance
- Consistenza dati

### 3. `test_config.py`
Configurazione per i test:
- Setup database di test
- Cleanup automatico
- Configurazione ambiente

## Fixture Disponibili

### Fixture Base
- `test_order` - Singolo ordine di test
- `test_orders` - Lista di ordini di test
- `test_order_detail` - Singolo dettaglio ordine
- `test_order_details` - Lista di dettagli ordine

### Fixture di Supporto
- `test_customer` - Cliente di test
- `test_address` - Indirizzo di test
- `test_order_state` - Stato ordine di test
- `test_platform` - Piattaforma di test
- `test_payment` - Metodo pagamento di test
- `test_shipping` - Spedizione di test
- `test_sectional` - Sezionale di test

## Come Eseguire i Test

### 1. Esecuzione Completa
```bash
python run_order_tests.py
```

### 2. Test Specifico
```bash
python run_order_tests.py test/routers/test_order.py
```

### 3. Con Pytest Diretto
```bash
# Test base
pytest test/routers/test_order.py -v

# Test avanzati
pytest test/routers/test_order_advanced.py -v

# Tutti i test Order
pytest test/routers/test_order*.py -v

# Con coverage
pytest test/routers/test_order*.py --cov=src/routers/order --cov-report=term-missing -v
```

## Copertura Test

### Endpoint Testati
- ✅ GET /orders/ (con filtri e paginazione)
- ✅ GET /orders/{id}
- ✅ POST /orders/
- ✅ PUT /orders/{id}
- ✅ DELETE /orders/{id}
- ✅ PATCH /orders/{id}/status
- ✅ PATCH /orders/{id}/payment
- ✅ GET /orders/{id}/details
- ✅ GET /orders/{id}/summary

### Scenari Testati
- ✅ Operazioni CRUD complete
- ✅ Autenticazione e autorizzazione
- ✅ Validazione parametri
- ✅ Gestione errori (404, 403, 401, 422)
- ✅ Filtri multipli
- ✅ Paginazione
- ✅ Workflow di business
- ✅ Casi limite
- ✅ Consistenza dati

### Ruoli e Permessi Testati
- ✅ ADMIN (tutti i permessi)
- ✅ USER (solo lettura)
- ✅ ORDINI (gestione ordini)
- ✅ FATTURAZIONE (fatturazione)
- ✅ PREVENTIVI (preventivi)

## Struttura Test

### Classi di Test
1. **TestOrderEndpoints** - Test funzionalità base
2. **TestOrderEndpointsAuthorization** - Test autorizzazione
3. **TestOrderEndpointsValidation** - Test validazione
4. **TestOrderAdvancedScenarios** - Test scenari avanzati

### Pattern di Test
- **Setup** - Preparazione dati di test
- **Action** - Esecuzione operazione
- **Assert** - Verifica risultato
- **Cleanup** - Pulizia automatica

## Dati di Test

### Ordine di Test
```json
{
  "id_origin": 1,
  "id_address_delivery": 1,
  "id_address_invoice": 1,
  "id_customer": 1,
  "id_platform": 1,
  "id_payment": 1,
  "id_shipping": 1,
  "id_sectional": 1,
  "id_order_state": 1,
  "is_invoice_requested": false,
  "is_payed": false,
  "total_weight": 1.5,
  "total_price": 99.99,
  "cash_on_delivery": 0.0
}
```

### Dettaglio Ordine di Test
```json
{
  "id_order": 1,
  "id_product": 1,
  "product_name": "Climatizzatore Daikin",
  "product_reference": "DAI-123",
  "product_qty": 2,
  "product_price": 49.99,
  "product_weight": 0.75,
  "rda": "RDA123"
}
```

## Configurazione Ambiente

### Variabili d'Ambiente
- `SECRET_KEY` - Chiave segreta per JWT
- `MAX_LIMIT` - Limite massimo per paginazione
- `LIMIT_DEFAULT` - Limite predefinito

### Database di Test
- SQLite in memoria
- Cleanup automatico
- Isolamento tra test

## Troubleshooting

### Errori Comuni
1. **Database non trovato** - Verifica che il database di test sia configurato
2. **Fixture non trovate** - Verifica che le fixture siano importate correttamente
3. **Permessi negati** - Verifica la configurazione di autenticazione nei test

### Debug
```bash
# Esegui test con output dettagliato
pytest test/routers/test_order.py -v -s

# Esegui test specifico con debug
pytest test/routers/test_order.py::TestOrderEndpoints::test_get_all_orders_success -v -s
```

## Estensione Test

### Aggiungere Nuovi Test
1. Crea nuovo metodo nella classe appropriata
2. Usa le fixture esistenti o crea nuove
3. Segui il pattern Setup-Action-Assert
4. Aggiungi cleanup se necessario

### Aggiungere Nuove Fixture
1. Aggiungi fixture in `test/utils.py`
2. Usa `@pytest.fixture()` decorator
3. Implementa setup e cleanup
4. Documenta la fixture

## Metriche di Qualità

### Obiettivi
- **Copertura**: > 90%
- **Test per endpoint**: > 5 test
- **Scenari edge**: Coperti
- **Performance**: < 1s per test

### Monitoraggio
- Esegui test regolarmente
- Monitora coverage
- Verifica performance
- Aggiorna test per nuove funzionalità
