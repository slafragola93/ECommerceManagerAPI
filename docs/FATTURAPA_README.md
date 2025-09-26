# Servizio FatturaPA - Documentazione

## Panoramica

Il servizio FatturaPA è un modulo completo per la generazione e gestione di fatture elettroniche secondo le specifiche tecniche italiane. Il servizio supporta:

- ✅ Validazione completa secondo specifiche FatturaPA
- ✅ Generazione XML deterministico
- ✅ Mapping automatico da Order a FatturaPA
- ✅ Gestione campi opzionali
- ✅ Supporto per persona fisica e giuridica
- ✅ Integrazione con API FatturaPA

## Architettura

### Componenti Principali

1. **Enums** (`src/models/fatturapa_enums.py`)
   - Domini validi per tutti i campi FatturaPA
   - RegimeFiscale, TipoDocumento, ModalitaPagamento, etc.

2. **Modelli Pydantic** (`src/schemas/fatturapa_models.py`)
   - Validazione completa con regole incrociate
   - Gestione cardinalità e obbligatorietà
   - Supporto per campi opzionali

3. **Serializer XML** (`src/services/fatturapa_serializer.py`)
   - Generazione XML deterministico
   - Ordinamento tag coerente
   - Gestione automatica campi opzionali

4. **Servizio Business** (`src/services/fatturapa_service.py`)
   - Mapping da Order a FatturaPA
   - Integrazione con API FatturaPA
   - Gestione upload e invio

5. **Endpoints FastAPI** (`src/routers/fatturapa.py`)
   - API REST per tutte le operazioni
   - Validazione e generazione XML
   - Recupero dati da ID ordine

## Endpoints Disponibili

### 1. Validazione Fattura
```http
POST /fatturapa/validate
Content-Type: application/json

{
  "fattura": {
    "fattura_elettronica_header": { ... },
    "fattura_elettronica_body": { ... }
  }
}
```

**Response:**
```json
{
  "valid": true,
  "errors": []
}
```

### 2. Generazione XML da JSON
```http
POST /fatturapa/xml
Content-Type: application/json

{
  "fattura": { ... }
}
```

**Response:**
```json
{
  "status": "success",
  "xml_content": "<?xml version='1.0' encoding='UTF-8'?>...",
  "filename": "fattura_20240115_143022.xml"
}
```

### 3. Generazione XML da ID Ordine
```http
GET /fatturapa/orders/{order_id}/xml?formato_trasmissione=FPR12&codice_destinatario=1234567
```

**Parametri Opzionali:**
- `codice_destinatario`: Se non fornito, viene recuperato dal campo `sdi` dell'indirizzo di fatturazione
- `pec_destinatario`: Se non fornito, viene recuperato dal campo `pec` dell'indirizzo di fatturazione
- `progressivo_invio`: Se non fornito, viene auto-generato dall'ID ordine

**Response:**
```json
{
  "status": "success",
  "order_id": 123,
  "invoice_id": 456,
  "document_number": "00001",
  "filename": "IT12345678901_00001.xml",
  "message": "Fattura generata e caricata con successo"
}
```

### 4. Recupero Dati Ordine
```http
GET /fatturapa/orders/{order_id}/data
```

**Response:**
```json
{
  "status": "success",
  "order_id": 123,
  "order_data": {
    "id_order": 123,
    "total_price": 122.00,
    "invoice_firstname": "Mario",
    "invoice_lastname": "Rossi",
    "invoice_company": "Azienda Test SRL",
    "invoice_address1": "Via Roma 123",
    "invoice_postcode": "00100",
    "invoice_city": "Roma",
    "invoice_state": "RM",
    "invoice_vat": "12345678901",
    "invoice_dni": "RSSMRA80A01H501U",
    "invoice_pec": "test@pec.it"
  },
  "order_details": [
    {
      "id_order_detail": 1,
      "product_name": "Prodotto Test",
      "product_price": 100.00,
      "product_qty": 1,
      "id_tax": 1
    }
  ]
}
```

### 5. Verifica API FatturaPA
```http
GET /fatturapa/verify
```

### 6. Recupero Eventi
```http
GET /fatturapa/events
```

### 7. Generazione e Download XML
```http
GET /fatturapa/orders/{order_id}/xml-only
```

**Response**: File XML scaricabile direttamente dal browser
- **Content-Type**: `application/xml`
- **Filename**: `{VAT_NUMBER}_{DOCUMENT_NUMBER}.xml`
- **Esempio**: `IT08632861210_00001.xml`

**Utilizzo:**
- Apri l'URL nel browser
- Il file XML verrà scaricato automaticamente
- Perfetto per test e verifica dell'XML generato

### 8. Validazione XML con Analisi Errori
```http
POST /fatturapa/orders/{order_id}/validate-xml
```

**Response:**
```json
{
  "status": "success",
  "order_id": 36,
  "document_number": "00001",
  "xml_content": "<?xml version='1.0' encoding='UTF-8'?>...",
  "validation_issues": [
    {
      "field": "anagrafica_cliente",
      "issue": "Manca nome/cognome o denominazione azienda",
      "severity": "error"
    },
    {
      "field": "codice_destinatario",
      "issue": "Codice destinatario SDI non specificato (usato 0000000)",
      "severity": "warning"
    }
  ],
  "data_summary": {
    "cliente_nome": "Mario Rossi",
    "cliente_azienda": "",
    "cliente_piva": "12345678901",
    "cliente_cf": "RSSMRA80A01H501U",
    "cliente_indirizzo": "Via Roma 123",
    "cliente_citta": "Roma",
    "codice_destinatario": "0000000",
    "pec_destinatario": null,
    "totale_ordine": 122.00,
    "numero_dettagli": 2
  },
  "message": "Validazione XML completata"
}
```

### 9. Dettagli Fattura
```http
GET /fatturapa/invoices/{invoice_id}
```

**Response:**
```json
{
  "status": "success",
  "invoice": {
    "id_invoice": 123,
    "id_order": 456,
    "document_number": "00001",
    "filename": "IT08632861210_00001.xml",
    "status": "uploaded",
    "upload_result": {
      "status": "success",
      "message": "Upload completato con successo"
    },
    "date_add": "2024-01-15T10:30:00",
    "date_upd": "2024-01-15T10:35:00",
    "xml_content_length": 3138
  },
  "message": "Dettagli fattura recuperati con successo"
}
```

## Mapping Dati da Order

Il servizio recupera automaticamente i dati necessari dall'ordine:

### Dati Cliente (da `id_address_invoice`)
- **Nome/Cognome**: `firstname`, `lastname`
- **Azienda**: `company`
- **Indirizzo**: `address1`, `address2`
- **CAP**: `postcode`
- **Città**: `city`
- **Provincia**: `state`
- **Paese**: `country` (via `id_country`)
- **P.IVA**: `vat`
- **Codice Fiscale**: `dni`
- **PEC**: `pec`
- **Codice SDI**: `sdi`
- **Telefono**: `phone`

### Dati Ordine
- **Numero**: `id_order`
- **Data**: `date_add`
- **Totale**: `total_price`
- **Dettagli**: da `order_details`

### Dati Prodotti
- **Nome**: `product_name`
- **Prezzo**: `product_price`
- **Quantità**: `product_qty`
- **Tassa**: da `id_tax` → `tax.rate`

## Regole di Validazione

### Obbligatorietà (A)
- **A=1**: Campo obbligatorio
- **A=0**: Campo opzionale

### Cardinalità (B)
- **B=1**: Un solo valore
- **B=N**: Lista di valori

### Lunghezze
- **String**: `min_length`, `max_length`
- **Decimal**: `decimal_places`, `max_digits`

### Domini
- **RegimeFiscale**: RF01-RF20
- **TipoDocumento**: TD01-TD29
- **ModalitaPagamento**: MP01-MP23
- **Natura**: N1-N7

### Regole Incrociate
- **Persona Fisica**: Nome + Cognome (no Denominazione)
- **Persona Giuridica**: Denominazione (no Nome/Cognome)
- **TD01-TD03**: AliquotaIVA ≠ 0

## Esempi di Utilizzo

### 1. Generazione Fattura da Ordine
```python
# Endpoint: GET /fatturapa/orders/123/xml
# Parametri query:
# - formato_trasmissione: FPR12 (default) o FPA12
# - progressivo_invio: auto-generato se non fornito
# - codice_destinatario: 1234567 (opzionale, recuperato da address.sdi se non fornito)
# - pec_destinatario: test@pec.it (opzionale, recuperato da address.pec se non fornito)

# Esempio 1: Recupero automatico da indirizzo
GET /fatturapa/orders/123/xml
# Il sistema recupera automaticamente codice_destinatario e pec_destinatario dall'indirizzo

# Esempio 2: Override manuale
GET /fatturapa/orders/123/xml?codice_destinatario=9999999&pec_destinatario=custom@pec.it
# I valori forniti manualmente hanno precedenza su quelli dell'indirizzo
```

### 2. Validazione Manuale
```python
# Endpoint: POST /fatturapa/validate
{
  "fattura": {
    "fattura_elettronica_header": {
      "dati_trasmissione": {
        "id_trasmittente": {
          "id_paese": "IT",
          "id_codice": "12345678901"
        },
        "progressivo_invio": "00001",
        "formato_trasmissione": "FPR12",
        "codice_destinatario": "1234567"
      },
      "cedente_prestatore": {
        "dati_anagrafici": {
          "id_fiscale_iva": {
            "id_paese": "IT",
            "id_codice": "12345678901"
          },
          "anagrafica": {
            "denominazione": "Azienda Test SRL"
          },
          "regime_fiscale": "RF01"
        },
        "sede": {
          "indirizzo": "Via Roma 123",
          "cap": "00100",
          "comune": "Roma",
          "provincia": "RM",
          "nazione": "IT"
        },
        "contatti": {
          "telefono": "0612345678",
          "email": "info@aziendatest.it"
        }
      },
      "cessionario_committente": {
        "dati_anagrafici": {
          "id_fiscale_iva": {
            "id_paese": "IT",
            "id_codice": "98765432109"
          },
          "anagrafica": {
            "denominazione": "Cliente Test SRL"
          },
          "regime_fiscale": "RF01"
        },
        "sede": {
          "indirizzo": "Via Milano 456",
          "cap": "20100",
          "comune": "Milano",
          "provincia": "MI",
          "nazione": "IT"
        }
      }
    },
    "fattura_elettronica_body": {
      "dati_generali": {
        "dati_generali_documento": {
          "tipo_documento": "TD01",
          "divisa": "EUR",
          "data": "2024-01-15",
          "numero": "FAT-001",
          "importo_totale_documento": 122.00
        }
      },
      "dati_beni_servizi": {
        "dettaglio_linee": [
          {
            "numero_linea": 1,
            "descrizione": "Prodotto Test",
            "quantita": 1.00,
            "prezzo_unitario": 100.00,
            "prezzo_totale": 100.00,
            "aliquota_iva": 22.00
          }
        ],
        "dati_riepilogo": [
          {
            "aliquota_iva": 22.00,
            "imponibile_importo": 100.00,
            "imposta": 22.00
          }
        ]
      }
    }
  }
}
```

## Configurazione

### Variabili d'Ambiente
```bash
# API FatturaPA
FATTURAPA_API_KEY=your_api_key
FATTURAPA_BASE_URL=https://api.fatturapa.com/ws/V10.svc/rest

# Dati Azienda
COMPANY_VAT_NUMBER=12345678901
COMPANY_NAME=Azienda Test SRL
COMPANY_ADDRESS=Via Roma 123
COMPANY_CAP=00100
COMPANY_CITY=Roma
COMPANY_PROVINCE=RM
COMPANY_PHONE=0612345678
COMPANY_EMAIL=info@aziendatest.it
```

### Database
```sql
-- Esegui migrazione per nuovi campi
alembic upgrade head
```

## Test

### Esecuzione Test
```bash
# Test completi
pytest test/test_fatturapa_serializer.py -v

# Test specifico
pytest test/test_fatturapa_serializer.py::TestFatturaPASerializer::test_serialize_minimal_fattura -v
```

### Copertura Test
```bash
pytest test/test_fatturapa_serializer.py --cov=src.services.fatturapa_serializer --cov-report=html
```

## Errori Comuni

### 1. Validazione Fallita
```json
{
  "valid": false,
  "errors": [
    {
      "code": "VALIDATION_ERROR",
      "message": "IdCodice deve contenere solo caratteri alfanumerici",
      "path": "dati_trasmissione.id_trasmittente.id_codice"
    }
  ]
}
```

### 2. Errore Upload FatturaPA
```json
{
  "status": "error",
  "message": "Fattura generata ma upload fallito",
  "invoice_id": 123,
  "document_number": "00001",
  "filename": "IT08632861210_00001.xml",
  "upload_result": {
    "status": "error",
    "message": "Validation failed for one or more entities"
  }
}
```

**Soluzioni:**
1. **Verifica API**: Controlla che l'API FatturaPA sia configurata correttamente
2. **Controlla XML**: Verifica che l'XML generato sia valido
3. **Dettagli Errore**: Usa `GET /fatturapa/invoices/{invoice_id}` per vedere i dettagli completi
4. **Diagnostica**: Usa `POST /fatturapa/orders/{order_id}/validate-xml` per identificare i problemi specifici
5. **XML Solo**: Usa `GET /fatturapa/orders/{order_id}/xml-only` per generare XML senza upload

### 3. Diagnostica Errori di Validazione

Per identificare gli errori specifici nell'XML generato:

```http
POST /fatturapa/orders/36/validate-xml
```

Questo endpoint:
- ✅ Genera l'XML senza upload
- ✅ Analizza i dati per identificare problemi
- ✅ Fornisce un riepilogo completo dei dati
- ✅ Identifica errori e warning specifici

**Errori Comuni Identificati:**
- **Anagrafica Cliente**: Nome/cognome o denominazione mancante
- **Identificazione**: P.IVA o Codice Fiscale mancante  
- **Indirizzo**: Indirizzo cliente mancante
- **Dettagli Ordine**: Nessun dettaglio ordine trovato
- **Codice SDI**: Codice destinatario non specificato
- **Totale**: Totale ordine zero o negativo

### 2. Campi Obbligatori Mancanti
```json
{
  "valid": false,
  "errors": [
    {
      "code": "MISSING_REQUIRED_FIELD",
      "message": "Campo obbligatorio mancante",
      "path": "dati_trasmissione.progressivo_invio"
    }
  ]
}
```

### 3. Cardinalità Violata
```json
{
  "valid": false,
  "errors": [
    {
      "code": "CARDINALITY_ERROR",
      "message": "Campo accetta un solo valore",
      "path": "dati_trasmissione.progressivo_invio"
    }
  ]
}
```

## Note Tecniche

### Precisione Decimali
- **Importi**: 2 decimali (es. 100.00)
- **Aliquote**: 2 decimali (es. 22.00)
- **Quantità**: 2 decimali (es. 1.50)

### Formato Date
- **ISO 8601**: YYYY-MM-DD (es. 2024-01-15)

### Encoding XML
- **UTF-8** con dichiarazione XML
- **Namespace**: `http://www.fatturapa.gov.it/sdi/messaggi/v1.0`

### Ordinamento Tag
- **Header** → **Body**
- **DatiTrasmissione** → **CedentePrestatore** → **CessionarioCommittente**
- **DatiGenerali** → **DatiBeniServizi** → **DatiPagamento**

## Supporto

Per problemi o domande:
1. Controlla i log dell'applicazione
2. Verifica la configurazione API
3. Consulta la documentazione ufficiale FatturaPA
4. Contatta il team di sviluppo

## Changelog

### v1.0.0
- ✅ Implementazione completa servizio FatturaPA
- ✅ Validazione secondo specifiche tecniche
- ✅ Generazione XML deterministico
- ✅ Mapping automatico da Order
- ✅ Endpoints FastAPI completi
- ✅ Test suite completa
- ✅ Documentazione dettagliata
