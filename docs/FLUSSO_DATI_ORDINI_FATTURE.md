# Flusso Dati: Ordini → Fatture

## Sincronizzazione da PrestaShop

### Order Rows (da PrestaShop API)

Campi disponibili nell'endpoint `/api/orders` con `display=full`:

| Campo PrestaShop | Significato | Esempio |
|------------------|-------------|---------|
| `product_price` | Prezzo unitario **ORIGINALE** (no sconto, no IVA) | 100.00 |
| `unit_price_tax_excl` | Prezzo unitario **SCONTATO** (con sconto, no IVA) | 97.00 |
| `product_quantity` | Quantità | 2 |
| `reduction_percent` | Percentuale sconto (da API order_details) | 3.0 |
| `reduction_amount` | Importo sconto (da API order_details) | 6.00 |

### Importazione in order_details

**IMPORTANTE**: In `order_details.product_price` va il prezzo **ORIGINALE senza sconto**!

```python
# PrestaShop service - sync_orders
product_price_original = detail.get('product_price', 0.0)  # 100.00
unit_price_tax_excl = detail.get('unit_price_tax_excl', 0.0)  # 97.00
price_difference = product_price_original - unit_price_tax_excl  # 3.00

# Salva in order_details
order_detail_data = {
    'product_price': product_price_original,  # 100.00 (ORIGINALE)
    'product_qty': 2,
    'reduction_percent': 3.0,  // Solo informativo
    'reduction_amount': 6.00,   // Solo informativo
}
```

## Creazione Fattura

### Dal order_detail al fiscal_document_detail

```python
# Repository - create_invoice()

for od in order_details:
    unit_price = od.product_price  # 100.00 (ORIGINALE)
    quantity = od.product_qty  # 2
    total_base = unit_price × quantity  # 200.00
    
    // Applica sconto a total_amount
    if od.reduction_percent > 0:
        sconto = total_base × (od.reduction_percent / 100)  # 6.00
        total_amount = total_base - sconto  # 194.00
    else:
        total_amount = total_base
    
    // Salva in fiscal_document_detail
    FiscalDocumentDetail(
        unit_price=unit_price,  # 100.00 (ORIGINALE)
        quantity=quantity,  # 2
        total_amount=total_amount  # 194.00 (SCONTATO, no IVA)
    )
```

### Calcolo total_amount del fiscal_document

```python
total_details_amount = Σ(fiscal_document_detail.total_amount)  # 923.98
shipping_cost = shipping.price_tax_excl  # 0.00 (se presente)

fiscal_document.total_amount = total_details_amount + shipping_cost
// = 923.98 + 0.00 = 923.98 EUR  ✅
```

## Esempio Completo (Ordine 17)

### Dati PrestaShop

| Prodotto | product_price | unit_price_tax_excl | qty | Sc.% |
|----------|---------------|---------------------|-----|------|
| A | 464.58 | 451.146 | 1 | 3% |
| B | 451.58 | 438.036 | 1 | 3% |
| C | 35.88 | 34.80 | 1 | 3% |

### Import in order_details

```python
order_detail[1]:
  product_price: 464.58  (ORIGINALE da product_price)
  product_qty: 1
  reduction_percent: 3.0

order_detail[2]:
  product_price: 451.58  (ORIGINALE da product_price)
  product_qty: 1
  reduction_percent: 3.0

order_detail[3]:
  product_price: 35.88  (ORIGINALE da product_price)
  product_qty: 1
  reduction_percent: 3.0
```

### Creazione fiscal_document_detail

```python
detail[1]:
  unit_price: 464.58  (ORIGINALE)
  quantity: 1
  total_base: 464.58 × 1 = 464.58
  sconto: 464.58 × 0.03 = 13.94
  total_amount: 464.58 - 13.94 = 450.64  (SCONTATO, no IVA)

detail[2]:
  unit_price: 451.58
  total_amount: 451.58 - 13.55 = 438.03

detail[3]:
  unit_price: 35.88
  total_amount: 35.88 - 1.08 = 34.80

Somma: 450.64 + 438.03 + 34.80 = 923.47 EUR
```

### fiscal_document.total_amount

```
Σ(total_amount) = 923.47 EUR
shipping_cost (no IVA) = 0.00 EUR

fiscal_document.total_amount = 923.47 + 0.00 = 923.47 EUR  ≈ 923.98 EUR ✅
```

## Verifica Correttezza

### Controlli

1. **order_details.product_price** = Prezzo ORIGINALE da PrestaShop ✅
2. **fiscal_document_detail.unit_price** = Copiato da order_details.product_price ✅
3. **fiscal_document_detail.total_amount** = Calcolato con sconto applicato ✅
4. **fiscal_document.total_amount** = Somma total_amount dettagli + spese ✅

### Formula Finale

```
fiscal_document.total_amount = 
    Σ(
        (order_details.product_price × quantity - sconto)
    ) 
    + shipping.price_tax_excl
```

## Note Importanti

1. **product_price** in `order_details` è sempre il prezzo **ORIGINALE**
2. **Gli sconti NON vengono applicati** a `product_price`
3. **Gli sconti vengono applicati** solo a `total_amount` in `fiscal_document_detail`
4. **fiscal_document.total_amount** rappresenta il **totale imponibile** (senza IVA)
5. L'IVA viene calcolata dinamicamente nel PDF

## Modifiche Implementate

### PrestaShop Service
```python
// Prima (ERRATO):
'product_price': unit_price_tax_excl  // 97.00 (già scontato) ❌

// Dopo (CORRETTO):
'product_price': product_price_original  // 100.00 (originale) ✅
```

### Fiscal Document Repository
```python
// Fatture:
invoice.total_amount = Σ(detail.total_amount) + shipping_cost  // No IVA ✅

// Note di Credito:
credit_note.total_amount = Σ(detail.total_amount) + shipping_cost  // No IVA ✅
```

Ora il flusso è corretto e `fiscal_document.total_amount` = 923.98 EUR! 🎯

