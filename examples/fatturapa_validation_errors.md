# Errori di Validazione FatturaPA

## Validazioni Implementate

### 1. CodiceDestinatario
```python
# ERRORE se non è esattamente 7 caratteri
if len(codice_destinatario) != 7:
    raise ValueError(f"CodiceDestinatario deve essere esattamente 7 caratteri. Ricevuto: '{codice_destinatario}' (lunghezza: {len(codice_destinatario)})")
```

**Esempi di errore:**
- `"123456"` → Errore: lunghezza 6
- `"12345678"` → Errore: lunghezza 8
- `"0000000"` → ✅ Valido: lunghezza 7

### 2. CodiceFiscale
```python
# ERRORE se non è tra 11 e 16 caratteri
if len(customer_cf) < 11 or len(customer_cf) > 16:
    raise ValueError(f"CodiceFiscale deve essere tra 11 e 16 caratteri. Ricevuto: '{customer_cf}' (lunghezza: {len(customer_cf)})")
```

**Esempi di errore:**
- `"125325"` → Errore: lunghezza 6
- `"123456789012345678"` → Errore: lunghezza 18
- `"12345678901"` → ✅ Valido: lunghezza 11
- `"1234567890123456"` → ✅ Valido: lunghezza 16

### 3. Indirizzo
```python
# ERRORE se vuoto dopo pulizia
if not indirizzo_pulito:
    raise ValueError("Indirizzo cliente non può essere vuoto")
```

**Esempi di errore:**
- `""` → Errore: vuoto
- `"   "` → Errore: solo spazi
- `"Via Roma"` → ✅ Valido

### 4. Provincia
```python
# ERRORE se non è esattamente 2 caratteri
if not provincia or len(provincia) != 2:
    raise ValueError(f"Provincia deve essere esattamente 2 caratteri. Ricevuto: '{provincia}' (lunghezza: {len(provincia) if provincia else 0})")
```

**Esempi di errore:**
- `"M"` → Errore: lunghezza 1
- `"MIL"` → Errore: lunghezza 3
- `"MI"` → ✅ Valido: lunghezza 2
- `"NA"` → ✅ Valido: lunghezza 2

### 5. CAP
```python
# ERRORE se non è esattamente 5 caratteri
if not cap or len(cap) != 5:
    raise ValueError(f"CAP deve essere esattamente 5 caratteri. Ricevuto: '{cap}' (lunghezza: {len(cap) if cap else 0})")
```

**Esempi di errore:**
- `"2010"` → Errore: lunghezza 4
- `"201001"` → Errore: lunghezza 6
- `"20100"` → ✅ Valido: lunghezza 5

## Gestione Errori

### Endpoint che possono sollevare errori:
- `GET /fatturapa/orders/{order_id}/xml`
- `GET /fatturapa/orders/{order_id}/xml-only`
- `POST /fatturapa/orders/{order_id}/validate-xml`

### Esempio di risposta di errore:
```json
{
  "detail": "CodiceDestinatario deve essere esattamente 7 caratteri. Ricevuto: '123456' (lunghezza: 6)"
}
```

### HTTP Status Code:
- `400 Bad Request` per errori di validazione
- `500 Internal Server Error` per errori di sistema

## Correzioni Suggerite

### Per CodiceDestinatario:
1. **Se usi PEC**: Usa `"0000000"`
2. **Se hai codice SDI**: Assicurati che sia esattamente 7 caratteri
3. **Se non hai né PEC né SDI**: Usa `"0000000"`

### Per CodiceFiscale:
1. **Se è una P.IVA italiana**: 11 caratteri numerici
2. **Se è un CF italiano**: 16 caratteri alfanumerici
3. **Se non è valido**: Ometti il campo

### Per Indirizzo:
1. **Rimuovi virgole**: `"Via Roma, 123"` → `"Via Roma 123"`
2. **Rimuovi caratteri speciali**: `"Via Roma; 123"` → `"Via Roma 123"`
3. **Assicurati che non sia vuoto**

### Per Provincia:
1. **Usa codice a 2 lettere**: `"Milano"` → `"MI"`
2. **Maiuscolo**: `"mi"` → `"MI"`

### Per CAP:
1. **Solo numeri**: `"20100"`
2. **Esattamente 5 cifre**: `"2010"` → `"20100"`

