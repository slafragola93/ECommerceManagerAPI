# Test per la Sincronizzazione PrestaShop

Questo documento descrive i test implementati per la route di sincronizzazione PrestaShop.

## File di Test

### 1. `test_sync.py`
Test di base per la sincronizzazione:
- Test sincronizzazione completa
- Test sincronizzazione incrementale
- Test metodi di sincronizzazione individuali
- Test gestione errori
- Test autenticazione

### 2. `test_sync_integration.py`
Test di integrazione con dati mock:
- Test con dati limitati (max 10 elementi)
- Test sincronizzazione incrementale vs completa
- Test metodi individuali con dati reali
- Test gestione errori con dati limitati

### 3. `test_sync_config.py`
Configurazione e fixture per i test:
- Mock dell'API PrestaShop
- Dati di test limitati
- Fixture per servizi mock
- Configurazione per test con massimo 10 elementi

### 4. `test_sync_comprehensive.py`
Test completi che coprono tutti i casi richiesti:
- Test con massimo 10 elementi
- Test sincronizzazione incrementale e completa
- Test con parametri diversi (new_elements, batch_size)
- Test performance
- Test scenari di errore

## Casi di Test Implementati

### 1. Chiamate Web Service con Massimo 10 Elementi

#### Test Sincronizzazione Completa
```python
async def test_full_sync_with_max_10_elements()
```
- Testa la sincronizzazione completa con dati limitati
- Verifica che vengano processati massimo 10 elementi
- Controlla la struttura della risposta

#### Test Sincronizzazione Incrementale
```python
async def test_incremental_sync_with_max_10_elements()
```
- Testa la sincronizzazione incrementale
- Verifica il parametro `new_elements=True`
- Controlla i conteggi degli elementi processati

#### Test Metodi Individuali
```python
async def test_individual_sync_methods_with_limited_data()
```
- Testa ogni singolo metodo di sincronizzazione:
  - `sync_languages` (2 elementi)
  - `sync_countries` (5 elementi)
  - `sync_brands` (5 elementi)
  - `sync_categories` (5 elementi)
  - `sync_carriers` (3 elementi)
  - `sync_products` (3 elementi)
  - `sync_customers` (3 elementi)
  - `sync_addresses` (2 elementi)
  - `sync_orders` (2 elementi)

### 2. Test con Valori Incrementali e Full

#### Test Sincronizzazione Incrementale vs Completa
```python
async def test_incremental_sync_with_new_elements_false()
```
- Testa `new_elements=False` (sincronizzazione completa)
- Testa `new_elements=True` (sincronizzazione incrementale)
- Verifica i parametri passati al servizio

#### Test con Parametri Diversi
```python
async def test_sync_with_different_parameters()
```
- Testa combinazioni di parametri:
  - `batch_size=5&new_elements=true`
  - `batch_size=20&new_elements=false`
  - `new_elements=true` (incremental)
  - `new_elements=false` (full)

### 3. Test di Performance e Limitazioni

#### Test con Batch Size Limitato
```python
async def test_sync_with_batch_size_10()
```
- Testa sincronizzazione con `batch_size=10`
- Verifica che il servizio sia inizializzato correttamente
- Controlla i conteggi degli elementi processati

#### Test Performance
```python
async def test_sync_performance_with_limited_data()
```
- Misura il tempo di esecuzione
- Verifica che la risposta sia veloce (< 1 secondo)
- Testa con dati limitati per performance ottimali

### 4. Test di Gestione Errori

#### Test Scenari di Errore
```python
async def test_sync_error_scenarios()
```
- Piattaforma non trovata
- Piattaforma inattiva
- Errore del servizio API
- Gestione eccezioni

#### Test Autenticazione
```python
async def test_sync_authentication_requirements()
```
- Verifica che sia richiesta autenticazione
- Testa accesso non autorizzato

## Dati di Test

### Struttura Dati Mock
I test utilizzano dati mock limitati per simulare le chiamate API:

```python
# Esempio per products
'products': {
    'products': {
        'product': [
            {
                'id': '1',
                'id_manufacturer': '1',
                'id_category_default': '1',
                'name': [{'id': '1', 'value': 'Product 1'}],
                'reference': 'REF001',
                'ean13': '1234567890123',
                'weight': '1.0',
                # ... altri campi
            }
            # Massimo 3 prodotti per i test
        ]
    }
}
```

### Conteggi Attesi
```python
expected_counts = {
    'languages': 2,
    'countries': 5,
    'brands': 5,
    'categories': 5,
    'carriers': 3,
    'products': 3,
    'customers': 3,
    'addresses': 2,
    'orders': 2,
    'total': 10
}
```

## Esecuzione dei Test

### Eseguire Tutti i Test di Sincronizzazione
```bash
pytest test/routers/test_sync*.py -v
```

### Eseguire Test Specifici
```bash
# Test di base
pytest test/routers/test_sync.py -v

# Test di integrazione
pytest test/routers/test_sync_integration.py -v

# Test completi
pytest test/routers/test_sync_comprehensive.py -v
```

### Eseguire Test con Output Dettagliato
```bash
pytest test/routers/test_sync*.py -v -s --tb=short
```

## Copertura dei Test

I test coprono:

✅ **Sincronizzazione completa** con dati limitati (max 10 elementi)
✅ **Sincronizzazione incrementale** vs completa
✅ **Tutti i metodi individuali** di sincronizzazione
✅ **Parametri diversi** (new_elements, batch_size)
✅ **Gestione errori** e scenari di fallimento
✅ **Autenticazione** e autorizzazione
✅ **Performance** con dati limitati
✅ **Struttura delle risposte** e conteggi

## Mock e Fixture

### Mock PrestaShopService
- Simula le chiamate API
- Restituisce dati limitati
- Gestisce errori e eccezioni

### Mock PlatformRepository
- Simula la configurazione della piattaforma
- Gestisce scenari di errore (piattaforma non trovata, inattiva)

### Fixture di Test
- `mock_prestashop_api`: API mock con dati limitati
- `mock_prestashop_service_with_limited_data`: Servizio mock
- `mock_platform_repository`: Repository mock
- `SyncTestData`: Classe con dati di test e conteggi attesi

## Note Importanti

1. **Dati Limitati**: Tutti i test utilizzano massimo 10 elementi per garantire performance
2. **Mock Completi**: I test non fanno chiamate API reali
3. **Copertura Completa**: Tutti i casi richiesti sono coperti
4. **Performance**: I test sono ottimizzati per esecuzione veloce
5. **Isolamento**: Ogni test è indipendente e pulisce i propri dati
