# E-commerce Synchronization System

## Overview

Il sistema di sincronizzazione e-commerce è progettato per importare dati da piattaforme e-commerce esterne (PrestaShop, Shopify, Magento, ecc.) in modo modulare e asincrono.

## Architettura

### Struttura modulare
```
src/services/ecommerce/
├── __init__.py
├── base_ecommerce_service.py      # Classe base astratta
├── prestashop_service.py          # Implementazione PrestaShop
├── shopify_service.py             # Implementazione Shopify (futuro)
└── magento_service.py             # Implementazione Magento (futuro)
```

### Endpoint disponibili
- `POST /api/v1/sync/prestashop` - Avvia sincronizzazione completa PrestaShop
- `POST /api/v1/sync/prestashop/incremental` - Avvia sincronizzazione incrementale PrestaShop
- `GET /api/v1/sync/prestashop/status` - Stato sincronizzazione
- `GET /api/v1/sync/prestashop/last-ids` - Ultimi ID importati per tabella
- `POST /api/v1/sync/test-connection` - Test connessione

## Configurazione PrestaShop

### 1. Configurare le credenziali
Le credenziali PrestaShop devono essere configurate nella tabella `platforms` con ID 1:

```sql
-- Inserire o aggiornare la piattaforma PrestaShop
INSERT INTO platforms (id_platform, name, url, api_key) 
VALUES (1, 'PrestaShop', 'https://yourstore.com/api', 'your_api_key_here')
ON DUPLICATE KEY UPDATE 
    name = 'PrestaShop',
    url = 'https://yourstore.com/api',
    api_key = 'your_api_key_here';
```

### 2. Usare lo script di inizializzazione
```bash
python scripts/init_prestashop_platform.py
```

## Utilizzo

### Avviare la sincronizzazione completa
```bash
curl -X POST "http://localhost:8000/api/v1/sync/prestashop" \
  -H "Authorization: Bearer your_token"
```

### Avviare la sincronizzazione incrementale
```bash
curl -X POST "http://localhost:8000/api/v1/sync/prestashop/incremental" \
  -H "Authorization: Bearer your_token"
```

### Vedere gli ultimi ID importati
```bash
curl -X GET "http://localhost:8000/api/v1/sync/prestashop/last-ids" \
  -H "Authorization: Bearer your_token"
```

### Testare la connessione
```bash
curl -X POST "http://localhost:8000/api/v1/sync/test-connection" \
  -H "Authorization: Bearer your_token"
```

## Flusso di sincronizzazione

### Sincronizzazione completa vs incrementale

#### **Sincronizzazione completa** (`/prestashop`)
- Importa **tutti** i dati da PrestaShop
- Utile per la prima importazione o reset completo
- Più lenta ma garantisce coerenza totale

#### **Sincronizzazione incrementale** (`/prestashop/incremental`)
- Importa **solo i dati nuovi** (ID origin > ultimo importato)
- Molto più veloce per aggiornamenti regolari
- Basata sull'ultimo ID origin importato per ogni tabella

### Fase 1: Tabelle base (senza dipendenze)
1. **Languages** (`ps_lang` → `lang`)
2. **Countries** (`ps_country_lang` → `country`)
3. **Brands** (`ps_manufacturer` → `brand`)
4. **Categories** (`ps_category` → `category`)
5. **Carriers** (`ps_carrier` → `carrier`)
6. **Tags** (`ps_tag` → `tag`)

### Fase 2: Tabelle dipendenti
1. **Products** (`ps_product` → `product`)
2. **Customers** (`ps_customer` → `customer`)
3. **Payments** (`ps_orders` → `payment`)
4. **Addresses** (`ps_address` → `address`)

### Fase 3: Tabelle complesse
1. **Orders** (`ps_orders` → `order`)
2. **Product Tags** (`ps_product_tag` → `producttag`)
3. **Order Details** (`ps_order_detail` → `order_detail`)

## Mappatura dati

### Languages
- `lang_name` ← `ps_lang.name`
- `iso_code` ← `ps_lang.iso_code`

### Countries
- `id_origin` ← `ps_country.id_country`
- `name` ← `ps_country_lang.name` (italiano)
- `iso_code` ← `ps_country.iso_code`

### Brands
- `id_origin` ← `ps_manufacturer.id_manufacturer`
- `name` ← `ps_manufacturer.name`

### Categories
- `id_origin` ← `ps_category.id_category`
- `name` ← `ps_category_lang.name` (italiano)

### Products
- `id_origin` ← `ps_product.id_product`
- `id_platform` ← 1 (PrestaShop)
- `id_category` ← da `ps_product.id_category_default`
- `id_brand` ← da `ps_product.id_manufacturer`
- `name` ← `ps_product_lang.name` (italiano)
- `sku` ← `ps_product.reference`
- `type` ← estratto da nome (dual/trial)

### Orders
- `id_origin` ← `ps_orders.id_order`
- `id_customer` ← da `ps_orders.id_customer`
- `id_payment` ← da `ps_orders.payment`
- `total_price` ← `ps_orders.total_paid_tax_excl`
- `is_invoice_requested` ← `ps_orders.fattura`

## Caratteristiche tecniche

### Sincronizzazione asincrona
- Utilizza `asyncio.gather()` per eseguire operazioni in parallelo
- Processamento in batch (5000 record per volta)
- Gestione errori con rollback parziale

### Gestione duplicati
- **Update**: I record esistenti vengono aggiornati
- **Identificazione**: Tramite `id_origin` per tracciare i record originali

### Logging
- Log dettagliati per ogni fase
- Statistiche di processamento
- Gestione errori con messaggi specifici

## Estensibilità

### Aggiungere nuove piattaforme
1. Creare una nuova classe che estende `BaseEcommerceService`
2. Implementare tutti i metodi astratti
3. Aggiungere endpoint nel router `sync.py`
4. Configurare le credenziali in `app_configurations`

### Esempio Shopify
```python
class ShopifyService(BaseEcommerceService):
    def _get_auth_headers(self) -> Dict[str, str]:
        return {
            'X-Shopify-Access-Token': self.api_key,
            'Content-Type': 'application/json'
        }
    
    async def sync_products(self) -> List[Dict[str, Any]]:
        # Implementazione specifica per Shopify
        pass
```

## TODO e miglioramenti futuri

### Funzionalità da implementare
- [ ] Logging persistente in database
- [ ] Sistema di retry per errori temporanei
- [ ] Sincronizzazione incrementale
- [ ] Webhook per sincronizzazioni automatiche
- [ ] Dashboard per monitoraggio sincronizzazioni

### Configurazioni da rivedere
- [ ] `is_complete_payment` logic per payments
- [ ] `id_platform` hardcoded values
- [ ] `id_shipping` default values
- [ ] `cash_on_delivery` logic
- [ ] `insured_value` calculation
- [ ] `product_price` field mapping

## Troubleshooting

### Errori comuni
1. **401 Unauthorized**: Verificare API key PrestaShop
2. **404 Not Found**: Verificare Base URL PrestaShop
3. **Timeout**: Ridurre batch_size o aumentare timeout
4. **Memory Error**: Processare meno record per volta
5. **XML Response Error**: Il sistema ora include automaticamente `output_format=JSON` in tutte le richieste
6. **Product Tags Error**: I tag dei prodotti vengono ora recuperati dall'endpoint `/api/products` nel campo `<tags>` invece che dall'inesistente `/api/product_tags`
7. **List Object Errors**: Corretti errori `'list' object has no attribute 'get'` e `'list' object has no attribute 'lower'` con gestione migliorata dei formati di risposta
8. **Order Details Endpoint**: Aggiunto fallback per endpoint `/api/order_detail` se `/api/order_details` fallisce
9. **Debug di Fine Sincronizzazione**: Aggiunto report dettagliato con emoji, statistiche complete e riepilogo errori
10. **Correzione KeyError**: Risolto errore `'phase_name'` nel debug finale con gestione robusta delle strutture dati
11. **Ottimizzazione API Calls**: Implementato sistema di cache per evitare chiamate duplicate agli endpoint orders
12. **Order Details dalle Associazioni**: Utilizzo corretto del campo `<associations><order_rows>` degli orders per recuperare i dettagli degli ordini secondo la documentazione ufficiale PrestaShop

### Struttura Order Details

Secondo la [documentazione ufficiale PrestaShop](https://devdocs.prestashop-project.org/1.7/webservice/resources/orders/), gli order details sono contenuti nel campo `<associations><order_rows>` degli orders:

```xml
<associations>
  <order_rows>
    <order_row>
      <id><![CDATA[]]></id>
      <product_id><![CDATA[]]></product_id>
      <product_attribute_id><![CDATA[]]></product_attribute_id>
      <product_quantity><![CDATA[]]></product_quantity>
      <product_name><![CDATA[]]></product_name>
      <product_reference><![CDATA[]]></product_reference>
      <product_ean13><![CDATA[]]></product_ean13>
      <product_isbn><![CDATA[]]></product_isbn>
      <product_upc><![CDATA[]]></product_upc>
      <product_price><![CDATA[]]></product_price>
      <id_customization><![CDATA[]]></id_customization>
      <unit_price_tax_incl><![CDATA[]]></unit_price_tax_incl>
      <unit_price_tax_excl><![CDATA[]]></unit_price_tax_excl>
    </order_row>
  </order_rows>
</associations>
```

### Debug
- Controllare i log della console per dettagli
- Verificare configurazioni in `app_configurations`
- Testare connessione con endpoint `/test-connection`
- Debug struttura risposta con endpoint `/debug-response`
