# Esempio: Recupero Automatico Codice SDI

## Scenario
Un ordine con ID 123 ha un indirizzo di fatturazione che contiene:
- `sdi`: "1234567" (codice SDI del cliente)
- `pec`: "cliente@pec.it" (PEC del cliente)

## Utilizzo

### 1. Recupero Automatico (Raccomandato)
```http
GET /fatturapa/orders/123/xml
```

**Risultato:**
- Il sistema recupera automaticamente `codice_destinatario = "1234567"` dal campo `sdi` dell'indirizzo
- Il sistema recupera automaticamente `pec_destinatario = "cliente@pec.it"` dal campo `pec` dell'indirizzo
- Nessun parametro manuale necessario

### 2. Override Manuale
```http
GET /fatturapa/orders/123/xml?codice_destinatario=9999999&pec_destinatario=custom@pec.it
```

**Risultato:**
- I valori forniti manualmente hanno precedenza
- `codice_destinatario = "9999999"` (override manuale)
- `pec_destinatario = "custom@pec.it"` (override manuale)

### 3. Recupero Dati Ordine
```http
GET /fatturapa/orders/123/data
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
    "invoice_pec": "cliente@pec.it",
    "invoice_sdi": "1234567"
  },
  "order_details": [...]
}
```

## Vantaggi

1. **Automatico**: Non serve specificare manualmente codice SDI e PEC
2. **Flessibile**: Possibilità di override manuale quando necessario
3. **Consistente**: I dati vengono sempre recuperati dall'indirizzo di fatturazione
4. **Sicuro**: Fallback a "0000000" se il codice SDI non è presente

## Note Tecniche

- Il campo `sdi` nella tabella `addresses` deve essere popolato con il codice SDI del cliente
- Il campo `pec` nella tabella `addresses` deve essere popolato con la PEC del cliente
- Se `sdi` è vuoto, viene usato "0000000" come fallback
- Se `pec` è vuoto, il campo PECDestinatario non viene emesso nell'XML

