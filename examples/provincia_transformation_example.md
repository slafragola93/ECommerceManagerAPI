# Esempio Trasformazione Provincia

## Logica Implementata

La provincia viene automaticamente trasformata per rispettare il formato FatturaPA:

```python
# Logica nel servizio
provincia = order_data.get('invoice_state')
if provincia:
    # Tronca alle prime due lettere e converti in maiuscolo
    provincia = provincia[:2].upper()
```

## Esempi di Trasformazione

### ✅ **Trasformazioni Automatiche**

| Input | Output | Note |
|-------|--------|------|
| `"Napoli"` | `"NA"` | Tronca a 2 caratteri + maiuscolo |
| `"Milano"` | `"MI"` | Tronca a 2 caratteri + maiuscolo |
| `"Roma"` | `"RO"` | Tronca a 2 caratteri + maiuscolo |
| `"Torino"` | `"TO"` | Tronca a 2 caratteri + maiuscolo |
| `"Firenze"` | `"FI"` | Tronca a 2 caratteri + maiuscolo |
| `"Bologna"` | `"BO"` | Tronca a 2 caratteri + maiuscolo |
| `"MI"` | `"MI"` | Già corretto, nessuna modifica |
| `"na"` | `"NA"` | Solo maiuscolo |

### ❌ **Errori (troppo corta)**

| Input | Output | Errore |
|-------|--------|--------|
| `"M"` | `"M"` | Errore: solo 1 carattere |
| `""` | `""` | Errore: vuoto |
| `None` | `None` | Errore: mancante |

## Debug Response

### Warning (Trasformazione)
```json
{
  "field": "Provincia",
  "issue": "Provincia verrà troncata: 'Napoli' → 'NA'",
  "value": "Napoli",
  "suggestion": "Risultato finale: NA",
  "severity": "warning"
}
```

### Errore (Troppo Corta)
```json
{
  "field": "Provincia",
  "issue": "Provincia troppo corta: 'M' → 'M' (richiesti: 2 caratteri)",
  "value": "M",
  "severity": "error"
}
```

## XML Generato

### Prima (Errore)
```xml
<Provincia>Napoli</Provincia>  <!-- 6 caratteri - ERRORE -->
```

### Ora (Corretto)
```xml
<Provincia>NA</Provincia>  <!-- 2 caratteri - OK -->
```

## Vantaggi

1. **Automatico**: Non richiede intervento manuale
2. **Flessibile**: Accetta nomi completi delle province
3. **Standard**: Converte sempre al formato FatturaPA
4. **Robusto**: Gestisce maiuscole/minuscole
5. **Debug**: Mostra la trasformazione nel debug

## Utilizzo

### Database
```sql
-- Puoi salvare nomi completi
UPDATE addresses SET state = 'Napoli' WHERE id_address = 123;
UPDATE addresses SET state = 'Milano' WHERE id_address = 124;
```

### API
```json
// L'API gestisce automaticamente la trasformazione
{
  "invoice_state": "Napoli"  // Diventa "NA" nell'XML
}
```

### Debug
```bash
GET /fatturapa/orders/36/debug
# Mostra: "Provincia verrà troncata: 'Napoli' → 'NA'"
```

## Note Tecniche

- **Troncamento**: `[:2]` prende i primi 2 caratteri
- **Maiuscolo**: `.upper()` converte in maiuscolo
- **Validazione**: Controlla che il risultato sia esattamente 2 caratteri
- **Errore**: Solo se l'input è troppo corto (< 2 caratteri)

