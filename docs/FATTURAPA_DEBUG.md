# Debug Dettagliato FatturaPA

## Endpoint di Debug

### 1. Debug Completo
```
GET /fatturapa/orders/{order_id}/debug
```

**Risposta:**
```json
{
  "order_id": 36,
  "order_data": {
    "total_price": 100.00,
    "invoice_address1": "Via Roma 123",
    "invoice_city": "Milano",
    "invoice_state": "MI",
    "invoice_postcode": "20100",
    "invoice_sdi": "1234567",
    "invoice_pec": "test@pec.it",
    "invoice_dni": "12345678901",
    "invoice_company": "Azienda SRL",
    "invoice_firstname": "Mario",
    "invoice_lastname": "Rossi"
  },
  "order_details": [
    {
      "product_name": "Prodotto A",
      "product_qty": 1,
      "product_price": 100.00
    }
  ],
  "validation_issues": [
    {
      "field": "CodiceDestinatario",
      "issue": "Lunghezza non valida: 6 caratteri (richiesti: 7)",
      "value": "123456",
      "severity": "error"
    }
  ],
  "warnings": [
    {
      "field": "Indirizzo",
      "issue": "Contiene caratteri speciali che potrebbero causare problemi",
      "value": "Via Roma, 123",
      "suggestion": "Rimuovi virgole e punti e virgola dall'indirizzo"
    }
  ],
  "suggestions": [
    {
      "field": "CodiceFiscale",
      "issue": "Non presente",
      "suggestion": "Aggiungi codice fiscale o P.IVA nell'indirizzo di fatturazione"
    }
  ],
  "stats": {
    "total_errors": 1,
    "total_warnings": 1,
    "total_suggestions": 1,
    "can_generate_xml": false
  }
}
```

### 2. Validazione XML
```
POST /fatturapa/orders/{order_id}/validate-xml
```

**Risposta:**
```json
{
  "status": "success",
  "order_id": 36,
  "document_number": "00001",
  "xml_content": "<?xml version='1.0' encoding='UTF-8'?>...",
  "validation_issues": [
    {
      "field": "CodiceDestinatario",
      "issue": "Lunghezza non valida",
      "severity": "error"
    }
  ],
  "data_summary": {
    "total_amount": 100.00,
    "customer_name": "Mario Rossi",
    "customer_company": "Azienda SRL",
    "codice_destinatario": "123456",
    "provincia": "MI",
    "cap": "20100"
  },
  "message": "Validazione XML completata"
}
```

### 3. Download XML
```
GET /fatturapa/orders/{order_id}/xml-only
```

**Risposta:** File XML scaricabile

## Tipi di Errori

### Errori Critici (severity: "error")
- **CodiceDestinatario**: Lunghezza diversa da 7 caratteri
- **CodiceFiscale**: Lunghezza non tra 11-16 caratteri
- **Indirizzo**: Vuoto o mancante
- **Provincia**: Lunghezza diversa da 2 caratteri
- **CAP**: Lunghezza diversa da 5 caratteri
- **DettagliOrdine**: Nessun dettaglio trovato
- **TotalPrice**: Totale non valido

### Warning (severity: "warning")
- **CodiceDestinatario**: Non presente (userà 0000000)
- **CodiceFiscale**: Non presente
- **Indirizzo**: Contiene caratteri speciali
- **DettagliOrdine**: Nome prodotto mancante
- **DettagliOrdine**: Prezzo prodotto non valido

### Suggerimenti (severity: "suggestion")
- **CodiceDestinatario**: Aggiungi codice SDI
- **CodiceFiscale**: Aggiungi codice fiscale o P.IVA
- **Indirizzo**: Rimuovi caratteri speciali

## Logging Dettagliato

Il servizio ora include logging dettagliato:

```
INFO: Generazione XML per documento 00001
INFO: Cliente: Mario Rossi
INFO: CodiceFiscale: 12345678901
INFO: SDI: 1234567
INFO: PEC: test@pec.it
INFO: Validazione CodiceDestinatario: '1234567' (lunghezza: 7)
INFO: CodiceDestinatario validato: 1234567
```

## Utilizzo per Debug

### 1. Controllo Pre-Generazione
```bash
# Controlla tutti i dati prima di generare XML
GET /fatturapa/orders/36/debug
```

### 2. Validazione XML
```bash
# Genera XML e valida
POST /fatturapa/orders/36/validate-xml
```

### 3. Download XML
```bash
# Scarica XML per ispezione manuale
GET /fatturapa/orders/36/xml-only
```

## Esempi di Correzioni

### CodiceDestinatario
```json
// ERRORE
{
  "field": "CodiceDestinatario",
  "issue": "Lunghezza non valida: 6 caratteri (richiesti: 7)",
  "value": "123456",
  "severity": "error"
}

// CORREZIONE: Aggiungi un carattere o usa 0000000
"1234567" o "0000000"
```

### Provincia
```json
// WARNING (trasformazione automatica)
{
  "field": "Provincia",
  "issue": "Provincia verrà troncata: 'Napoli' → 'NA'",
  "value": "Napoli",
  "suggestion": "Risultato finale: NA"
}

// ERRORE (troppo corta)
{
  "field": "Provincia",
  "issue": "Provincia troppo corta: 'M' → 'M' (richiesti: 2 caratteri)",
  "value": "M",
  "severity": "error"
}

// CORREZIONE: Assicurati che abbia almeno 2 caratteri
"Napoli" → "NA" (automatico)
"Milano" → "MI" (automatico)
```

### Indirizzo
```json
// WARNING
{
  "field": "Indirizzo",
  "issue": "Contiene caratteri speciali che potrebbero causare problemi",
  "value": "Via Roma, 123",
  "suggestion": "Rimuovi virgole e punti e virgola dall'indirizzo"
}

// CORREZIONE: Rimuovi caratteri speciali
"Via Roma 123"
```

## Statistiche Debug

```json
{
  "stats": {
    "total_errors": 2,      // Errori critici
    "total_warnings": 1,    // Warning
    "total_suggestions": 1, // Suggerimenti
    "can_generate_xml": false // Può generare XML?
  }
}
```

- **can_generate_xml: true** → Nessun errore critico, XML generabile
- **can_generate_xml: false** → Errori critici presenti, correggere prima
