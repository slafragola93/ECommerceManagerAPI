# Debug Dettagliato FatturaPA - Generazione XML

## Endpoint di Debug Avanzati

### 1. Debug Step-by-Step XML Generation
```
GET /fatturapa/orders/{order_id}/debug-xml-generation
```

**Risposta dettagliata:**
```json
{
  "order_id": 36,
  "document_number": "00001",
  "step_by_step": [
    {
      "step": 1,
      "name": "Verifica Dati Ordine",
      "status": "success",
      "details": {
        "total_price": 100.00,
        "has_invoice_address": true,
        "has_invoice_city": true,
        "has_invoice_state": true,
        "has_invoice_postcode": true,
        "has_invoice_sdi": true,
        "has_invoice_pec": false,
        "has_invoice_dni": true
      }
    },
    {
      "step": 2,
      "name": "Verifica Dettagli Ordine",
      "status": "success",
      "details": {
        "count": 2,
        "products": [
          {
            "name": "Prodotto A",
            "qty": 1,
            "price": 50.00
          },
          {
            "name": "Prodotto B", 
            "qty": 1,
            "price": 50.00
          }
        ]
      }
    },
    {
      "step": 3,
      "name": "Calcoli IVA",
      "status": "success",
      "details": {
        "tax_rate": 22.0,
        "totale_imponibile": 81.97,
        "totale_imposta": 18.03,
        "total_amount": 100.00
      }
    },
    {
      "step": 4,
      "name": "Validazioni Critiche",
      "status": "error",
      "details": {
        "validations": [
          {
            "field": "CodiceDestinatario",
            "status": "error",
            "value": "123456",
            "issue": "Lunghezza non valida"
          },
          {
            "field": "Provincia",
            "status": "success",
            "value": "Napoli → NA"
          }
        ],
        "error_count": 1
      }
    },
    {
      "step": 5,
      "name": "Generazione XML",
      "status": "error",
      "details": {
        "error": "CodiceDestinatario deve essere esattamente 7 caratteri",
        "error_type": "ValueError"
      }
    }
  ],
  "errors": [
    "CodiceDestinatario: '123456' (lunghezza: 6)"
  ],
  "warnings": [],
  "summary": {
    "can_generate_xml": false,
    "total_errors": 1,
    "total_warnings": 0,
    "steps_completed": 4,
    "total_steps": 5
  }
}
```

### 2. Debug Generale
```
GET /fatturapa/orders/{order_id}/debug
```

### 3. Validazione XML
```
POST /fatturapa/orders/{order_id}/validate-xml
```

## Logging Dettagliato

Il servizio ora include logging completo per ogni step:

### Log di Esempio
```
INFO: === INIZIO GENERAZIONE XML FATTURAPA ===
INFO: Documento: 00001
INFO: Order data keys: ['total_price', 'invoice_address1', ...]
INFO: Order details count: 2
INFO: === DATI CLIENTE ===
INFO: Cliente: 'Mario Rossi' (company: 'Azienda SRL')
INFO: CodiceFiscale: '12345678901' (lunghezza: 11)
INFO: SDI: '1234567' (lunghezza: 7)
INFO: PEC: 'test@pec.it'
INFO: === CALCOLI IVA ===
INFO: Aliquota IVA: 22.0%
INFO: === DETTAGLI ORDINE ===
INFO: --- Prodotto 1 ---
INFO:   Nome: 'Prodotto A'
INFO:   Quantità: 1
INFO:   Prezzo con IVA: 50.0
INFO:   Prezzo unitario netto: 40.9836
INFO:   Prezzo totale netto: 40.9836
INFO:   Imposta linea: 9.0164
INFO:   Prezzo totale netto (arrotondato): 40.98
INFO:   Imposta linea (arrotondata): 9.02
INFO: === TOTALI CALCOLATI ===
INFO: Totale imponibile: 81.97
INFO: Totale imposta: 18.03
INFO: Totale con IVA: 100.00
INFO: === CREAZIONE XML ===
INFO: Root element creato
INFO: === VALIDAZIONE CODICE DESTINATARIO ===
INFO: CodiceDestinatario: '1234567' (lunghezza: 7)
INFO: ✅ CodiceDestinatario validato: 1234567
INFO: === VALIDAZIONE CODICE FISCALE ===
INFO: CodiceFiscale: '12345678901' (lunghezza: 11)
INFO: ✅ CodiceFiscale validato: 12345678901
INFO: === VALIDAZIONE INDIRIZZO ===
INFO: Indirizzo originale: 'Via Roma 123'
INFO: Indirizzo pulito: 'Via Roma 123'
INFO: ✅ Indirizzo validato: Via Roma 123
INFO: === VALIDAZIONE CAP ===
INFO: CAP: '20100' (lunghezza: 5)
INFO: ✅ CAP validato: 20100
INFO: === VALIDAZIONE PROVINCIA ===
INFO: Provincia originale: 'Napoli'
INFO: Provincia elaborata: 'NA'
INFO: ✅ Provincia validata: NA
INFO: === FINALIZZAZIONE XML ===
INFO: XML generato con successo (lunghezza: 3147 caratteri)
INFO: === FINE GENERAZIONE XML FATTURAPA ===
```

## Step di Debug

### Step 1: Verifica Dati Ordine
- ✅ Controlla presenza di tutti i campi necessari
- ✅ Verifica total_price
- ✅ Controlla dati indirizzo fatturazione

### Step 2: Verifica Dettagli Ordine
- ✅ Conta prodotti nell'ordine
- ✅ Verifica nome, quantità, prezzo per ogni prodotto
- ❌ Errore se nessun dettaglio trovato

### Step 3: Calcoli IVA
- ✅ Calcola prezzo unitario netto
- ✅ Calcola imposta per linea
- ✅ Somma totali imponibile e imposta
- ✅ Arrotondamento ROUND_HALF_UP

### Step 4: Validazioni Critiche
- ✅ **CodiceDestinatario**: Lunghezza esatta 7 caratteri
- ✅ **CodiceFiscale**: Lunghezza 11-16 caratteri
- ✅ **Indirizzo**: Non vuoto
- ✅ **Provincia**: Trasformazione automatica (es. "Napoli" → "NA")
- ✅ **CAP**: Lunghezza esatta 5 caratteri

### Step 5: Generazione XML
- ✅ Crea struttura XML FatturaPA
- ✅ Aggiunge tutti gli elementi
- ✅ Converte in stringa
- ❌ Errore se validazioni falliscono

## Errori Comuni e Soluzioni

### CodiceDestinatario
```json
// ERRORE
{
  "field": "CodiceDestinatario",
  "status": "error",
  "value": "123456",
  "issue": "Lunghezza non valida"
}

// SOLUZIONE: Aggiungi un carattere o usa 0000000
"1234567" o "0000000"
```

### Provincia
```json
// SUCCESSO (trasformazione automatica)
{
  "field": "Provincia", 
  "status": "success",
  "value": "Napoli → NA"
}

// ERRORE (troppo corta)
{
  "field": "Provincia",
  "status": "error", 
  "value": "M",
  "issue": "Troppo corta"
}
```

### Dettagli Ordine
```json
// ERRORE
{
  "step": 2,
  "name": "Verifica Dettagli Ordine",
  "status": "error",
  "details": {
    "count": 0,
    "products": []
  }
}

// SOLUZIONE: Verifica che l'ordine abbia prodotti
```

## Utilizzo per Debug

### 1. Controllo Pre-Generazione
```bash
# Debug completo step-by-step
GET /fatturapa/orders/36/debug-xml-generation
```

### 2. Analisi Errori Specifici
```bash
# Debug generale con validazioni
GET /fatturapa/orders/36/debug
```

### 3. Test Generazione XML
```bash
# Prova a generare XML
GET /fatturapa/orders/36/xml-only
```

### 4. Controllo Log
```bash
# Controlla i log del server per dettagli completi
# I log mostrano ogni step della generazione
```

## Riepilogo Debug

```json
{
  "summary": {
    "can_generate_xml": false,    // Può generare XML?
    "total_errors": 2,            // Errori critici
    "total_warnings": 0,          // Warning
    "steps_completed": 3,         // Step completati
    "total_steps": 5              // Step totali
  }
}
```

- **can_generate_xml: true** → Nessun errore, XML generabile
- **can_generate_xml: false** → Errori presenti, correggere prima
- **steps_completed < total_steps** → Processo interrotto per errori

