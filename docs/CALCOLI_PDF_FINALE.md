# Calcoli Definitivi PDF Fatture

## Formula dei Calcoli

### Dettaglio Righe Prodotti

Per ogni riga nella tabella prodotti:

| Campo | Formula | Fonte Dati |
|-------|---------|------------|
| **Prezzo No IVA** | `unit_price` | `fiscal_document_details.unit_price` (già scontato) |
| **Quantità** | `quantity` | `fiscal_document_details.quantity` |
| **Sconto %** | `reduction_percent` | `fiscal_document_details.reduction_percent` (solo info) |
| **IVA %** | `vat_rate` | `fiscal_document_details.vat_rate` |
| **Totale** | `total_amount × (1 + IVA%)` | Calcolato con IVA inclusa |

**IMPORTANTE**: 
- `total_amount` è **già scontato**
- Lo sconto viene mostrato solo come informazione
- Il totale della riga include l'IVA

### Sommatorie

```python
# Somma di tutti i "Prezzo No IVA" (colonna Prezzo No IVA)
subtotal = Σ(total_amount)  # Imp. Merce / Merce netta

# Somma di tutti i "Totale" (colonna Totale con IVA)
merce_lorda = Σ(total_with_vat)  # Merce lorda
```

### Spese di Trasporto

```python
# Recupero da Shipments + Tax
shipping_cost = shipments.price_tax_excl  # Prezzo no IVA
shipping_vat_percentage = tax.percentage  # Da Tax.id_tax
shipping_cost_with_vat = shipping_cost × (1 + shipping_vat_percentage / 100)
shipping_vat = shipping_cost_with_vat - shipping_cost
```

### Totali Finali

```python
# Colonna sinistra
Merce netta = subtotal  # Somma "Prezzo No IVA"
Total imponibile = subtotal + shipping_cost
Merce lorda = total_with_vat_sum  # Somma "Totale"

# Colonna destra  
Total IVA = (merce_lorda - subtotal) + shipping_vat
Total documento = total_imponibile + total_vat
```

## Esempio Completo

### Dati Input

**Prodotti:**
| Codice | Desc | Qta | Prezzo No IVA | Sc.% | IVA | Totale |
|--------|------|-----|---------------|------|-----|--------|
| A001 | Prod A | 2 | 100.00 | 3% | 22% | 244.00 |
| A002 | Prod B | 1 | 50.00 | 0% | 22% | 61.00 |

**Spese Trasporto:**
- Costo no IVA: 10.00 EUR (da `shipments.price_tax_excl`)
- IVA: 22% (da `tax.percentage` via `shipments.id_tax`)

### Calcoli Passo per Passo

#### 1. Sommatorie dalle Righe

```
subtotal (Merce netta) = 100×2 + 50×1 = 250.00 EUR
total_with_vat_sum (Merce lorda) = 244.00 + 61.00 = 305.00 EUR
```

#### 2. Spese Trasporto

```
shipping_cost = 10.00 EUR
shipping_vat_percentage = 22%
shipping_cost_with_vat = 10.00 × 1.22 = 12.20 EUR
shipping_vat = 12.20 - 10.00 = 2.20 EUR
```

#### 3. Totali

```
Total imponibile = 250.00 + 10.00 = 260.00 EUR
IVA merce = 305.00 - 250.00 = 55.00 EUR
IVA spedizione = 2.20 EUR
Total IVA = 55.00 + 2.20 = 57.20 EUR
Total documento = 260.00 + 57.20 = 317.20 EUR
```

### Output PDF

**Tabella Riepilogo IVA:**
| Aliquota | Imp. Merce | Imp. Spese | Tot. IVA |
|----------|------------|------------|----------|
| 22% | 250.00 | 10.00 | 57.20 |

**Dettagli:**
```
Spese trasporto (+22% IVA)     12.20 EUR
```

**Totali:**
```
Colonna Sinistra:              Colonna Destra:
Merce netta:      250.00       Totale IVA:       57.20
Tot. imponibile:  260.00       Spese varie:      0.00
Spese incasso:    0.00
Merce lorda:      305.00       TOTALE DOCUMENTO: 317.20 EUR
```

## Verifica Calcoli

### Controlli di Coerenza

1. **Merce lorda = Merce netta + IVA merce**
   - 305.00 = 250.00 + 55.00 ✅

2. **Total IVA = IVA merce + IVA spedizione**
   - 57.20 = 55.00 + 2.20 ✅

3. **Total documento = Total imponibile + Total IVA**
   - 317.20 = 260.00 + 57.20 ✅

4. **Total documento = Merce lorda + Spese trasporto con IVA**
   - 317.20 = 305.00 + 12.20 ✅

## Struttura Dati

### Tabella fiscal_document_details
- `unit_price`: Prezzo unitario no IVA (già scontato)
- `total_amount`: Totale riga no IVA (già scontato)
- `reduction_percent`: Percentuale sconto (solo informativa)
- `vat_rate`: Aliquota IVA (%)
- `quantity`: Quantità

### Tabella shipments
- `price_tax_excl`: Prezzo spedizione no IVA
- `price_tax_incl`: Prezzo spedizione con IVA
- `id_tax`: FK a taxes per recuperare la percentuale

### Tabella taxes
- `percentage`: Percentuale IVA (es. 22 per 22%)

## Repository Utilizzati

### TaxRepository.get_percentage_by_id(id_tax)
Recupera la percentuale IVA dalla tabella taxes.

```python
from src.repository.tax_repository import TaxRepository

tax_repo = TaxRepository(db)
shipping_vat_percentage = tax_repo.get_percentage_by_id(order.shipments.id_tax)
```

## Note Implementative

- Tutti i prezzi sono in EUR
- Gli sconti sono già applicati nei prezzi (no ricalcolo)
- La colonna "Sc.%" è solo informativa
- Le spese trasporto vengono sempre recuperate da shipments
- La percentuale IVA viene sempre recuperata da taxes
- Fallback sicuri per valori mancanti

