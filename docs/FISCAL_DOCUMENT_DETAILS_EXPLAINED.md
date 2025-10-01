# Spiegazione fiscal_document_details

## Struttura Dati

### Tabella fiscal_document_details

| Campo | Significato | Calcolo | Esempio |
|-------|-------------|---------|---------|
| `unit_price` | Prezzo unitario **originale** (no sconto, no IVA) | Da `order_detail.product_price` | 100.00 EUR |
| `quantity` | Quantità | Da `order_detail.product_qty` | 2 |
| `total_amount` | Totale riga **scontato** (no IVA) | `(unit_price × quantity) - sconto` | 194.00 EUR |

### Calcolo total_amount nel Repository

```python
# src/repository/fiscal_document_repository.py - create_invoice()

unit_price = od.product_price  # 100.00 EUR
quantity = od.product_qty  # 2
total_base = unit_price * quantity  # 200.00 EUR

# Applica sconti
if od.reduction_percent and od.reduction_percent > 0:
    sconto = total_base * (od.reduction_percent / 100)
    total_amount = total_base - sconto
    # Esempio: 200.00 - (200.00 * 0.03) = 194.00 EUR
elif od.reduction_amount and od.reduction_amount > 0:
    total_amount = total_base - od.reduction_amount
else:
    total_amount = total_base
```

## Esempio Completo

### Dati OrderDetail
```
product_price = 100.00 EUR (prezzo unitario)
product_qty = 2
reduction_percent = 3%
```

### Calcolo nel Repository
```
unit_price = 100.00 EUR
quantity = 2
total_base = 100.00 × 2 = 200.00 EUR
sconto = 200.00 × 0.03 = 6.00 EUR
total_amount = 200.00 - 6.00 = 194.00 EUR
```

### Risultato fiscal_document_detail
```
unit_price = 100.00      (prezzo originale)
quantity = 2
total_amount = 194.00    (totale scontato no IVA)
```

## Visualizzazione nel PDF

### Tabella Prodotti

| Prezzo No IVA | Sc.% | IVA | Totale |
|---------------|------|-----|--------|
| 100.00 EUR | 3% | 22% | 236.68 EUR |

Dove:
- **Prezzo No IVA**: `unit_price` = 100.00 EUR (originale)
- **Sc.%**: `reduction_percent` = 3% (informativo)
- **IVA**: `vat_rate` = 22%
- **Totale**: `total_amount × (1 + IVA%)` = 194.00 × 1.22 = **236.68 EUR**

### Sommatorie

```python
# Imp. Merce / Merce netta (no IVA, già scontata)
subtotal = Σ(total_amount) = 194.00 EUR (per questa riga)

# Merce lorda (con IVA)
merce_lorda = Σ(total_amount × (1 + IVA%)) = 236.68 EUR (per questa riga)
```

## Domande Frequenti

### Q: Perché unit_price è 100 ma total_amount è 194?
**A**: Perché `total_amount` include:
- La moltiplicazione per quantità (100 × 2 = 200)
- L'applicazione dello sconto (200 - 6 = 194)

### Q: Dove viene mostrato il prezzo effettivo dopo lo sconto?
**A**: `total_amount / quantity` = 194 / 2 = 97.00 EUR (prezzo unitario scontato)

### Q: Come si calcola il totale con IVA?
**A**: `total_amount × (1 + IVA%)` = 194 × 1.22 = 236.68 EUR

### Q: Il campo unit_price include lo sconto?
**A**: **NO**, `unit_price` è il prezzo originale senza sconto.
È il campo `total_amount` che contiene il totale già scontato.

## Flusso Dati Completo

```
OrderDetail
├── product_price: 100.00 (unitario originale)
├── product_qty: 2
├── reduction_percent: 3%
└── → Calcolo nel repository →

FiscalDocumentDetail
├── unit_price: 100.00 (copiato da product_price)
├── quantity: 2 (copiato da product_qty)
└── total_amount: 194.00 (calcolato: unit × qty - sconto)

PDF Display
├── Prezzo No IVA: 100.00 (unit_price)
├── Quantità: 2
├── Sconto: 3%
├── IVA: 22%
└── Totale: 236.68 (total_amount × 1.22)
```

## Note Importanti

1. **unit_price** è sempre il prezzo originale (senza sconto)
2. **total_amount** è sempre scontato ma senza IVA
3. Lo sconto è già applicato in `total_amount`
4. Per il PDF, usiamo `total_amount` per i calcoli, non `unit_price × quantity`
5. La colonna "Prezzo No IVA" mostra `unit_price` per trasparenza
6. Ma i totali usano `total_amount` che è già scontato

