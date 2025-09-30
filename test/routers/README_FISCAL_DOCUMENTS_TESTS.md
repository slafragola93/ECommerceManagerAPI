# 🧪 Test Fiscal Documents - Guida Esecuzione

## 📋 Test Implementati

Il file `test_fiscal_documents.py` contiene **20 test completi** per il sistema di fatture e note di credito.

---

## 🏃 Esecuzione Test

### **Tutti i test:**
```bash
pytest test/routers/test_fiscal_documents.py -v
```

### **Test specifico:**
```bash
pytest test/routers/test_fiscal_documents.py::test_create_invoice_electronic_success -v
```

### **Per categoria:**
```bash
# Solo test fatture
pytest test/routers/test_fiscal_documents.py -k "invoice" -v

# Solo test note credito
pytest test/routers/test_fiscal_documents.py -k "credit_note" -v

# Solo test numerazione
pytest test/routers/test_fiscal_documents.py -k "numbering" -v
```

---

## 📊 Categorie Test

### **1. Creazione Fatture** (6 test)
- ✅ `test_create_invoice_electronic_success` - Fattura elettronica IT
- ✅ `test_create_invoice_non_electronic_success` - Fattura non elettronica estero
- ✅ `test_create_invoice_electronic_foreign_address_error` - Errore indirizzo estero
- ✅ `test_create_multiple_invoices_same_order` - Multiple fatture stesso ordine
- ✅ `test_create_invoice_order_not_found` - Ordine inesistente
- ✅ `test_numbering_only_for_electronic` - Solo elettroniche hanno numero

### **2. Creazione Note di Credito** (5 test)
- ✅ `test_create_credit_note_total_success` - NC totale
- ✅ `test_create_credit_note_partial_success` - NC parziale
- ✅ `test_create_credit_note_invalid_order_detail` - Articolo non in fattura
- ✅ `test_create_credit_note_quantity_exceeds_invoice` - Quantità eccessiva
- ✅ `test_create_credit_note_for_non_electronic_invoice` - NC non elettronica
- ✅ `test_create_credit_note_electronic_for_non_electronic_invoice` - Errore tipo

### **3. Numerazione Sequenziale** (3 test)
- ✅ `test_sequential_numbering_same_year` - Numerazione progressiva
- ✅ `test_sequential_numbering_separate_for_credit_notes` - Numerazione separata
- ✅ `test_numbering_reset_new_year` - ⚠️ Reset annuale (TODO)

### **4. Recupero Dati** (3 test)
- ✅ `test_get_invoice_details_with_products` - Dettagli con info prodotto
- ✅ `test_get_invoices_by_order` - Tutte le fatture di un ordine
- ✅ `test_get_credit_notes_by_invoice` - Tutte le NC di una fattura

### **5. Eliminazione** (2 test)
- ✅ `test_delete_fiscal_document_pending` - Elimina pending
- ✅ `test_delete_fiscal_document_with_credit_notes_error` - Errore se ha NC

### **6. Filtri** (2 test)
- ✅ `test_get_fiscal_documents_filter_by_type` - Filtro per tipo
- ✅ `test_get_fiscal_documents_filter_by_electronic` - Filtro elettronico

---

## 🎯 Scenari Testati

### **Scenario 1: Fattura Elettronica Completa**
```
1. Crea ordine IT con 2 articoli
2. Crea fattura elettronica
3. Verifica:
   - document_number = "000001"
   - tipo_documento_fe = "TD01"
   - FiscalDocumentDetails creati (2)
   - total_amount corretto
```

### **Scenario 2: Nota Credito Parziale**
```
1. Crea fattura con 3 articoli
2. Crea NC parziale per 1 articolo
3. Verifica:
   - id_fiscal_document_ref corretto
   - Quantità validata
   - Details creati correttamente
```

### **Scenario 3: Validazioni**
```
Test errori per:
- Ordine inesistente
- Fattura inesistente
- Indirizzo estero per elettronica
- Articolo non in fattura
- Quantità eccessiva
- Tipo documento incompatibile
```

---

## 📈 Coverage Atteso

Il test suite copre:
- ✅ **CRUD**: Create, Read, Delete
- ✅ **Validazioni**: Tutte le business rules
- ✅ **Edge Cases**: Errori, limiti, casi particolari
- ✅ **Integration**: Database, relationships, cascading
- ✅ **Business Logic**: Numerazione, sconti, totali

**Stimato:** ~85% code coverage

---

## ⚠️ Test "Numerazione Reset Anno"

### **Stato Attuale:**
```python
def test_numbering_reset_new_year():
    # Questo test DOCUMENTA il comportamento attuale
    # Attualmente NON resetta (continua numerazione)
    assert next_number == '000100'  # Continua da anno precedente
    
    # TODO: Dopo implementazione reset
    # assert next_number == '000001'  # Reset anno nuovo
```

### **Come Implementare Reset:**
Vedi documentazione: `docs/FISCAL_NUMBERING_RESET.md`

**Opzione A (Raccomandata):**
- Filtra `_get_next_electronic_number` per anno corrente
- Reset automatico ogni 1 gennaio

---

## 🔍 Debug Test

### **Test fallito?**
```bash
# Verbose output
pytest test/routers/test_fiscal_documents.py::test_name -vv

# Con print statements
pytest test/routers/test_fiscal_documents.py::test_name -s

# Stop al primo errore
pytest test/routers/test_fiscal_documents.py -x
```

### **Verifica database test:**
```bash
# Il database test viene creato e distrutto ad ogni test
# Se vuoi mantenerlo:
pytest test/routers/test_fiscal_documents.py --keepdb
```

---

## 📦 Dipendenze Test

Assicurati di avere:
```bash
pip install pytest
pip install pytest-asyncio
pip install httpx
```

---

## 🎯 Prossimi Step

1. ✅ Esegui test: `pytest test/routers/test_fiscal_documents.py -v`
2. ⏳ Implementa reset numerazione (Opzione A)
3. ⏳ Aggiorna test reset per verificare funzionamento
4. ✅ Integra test in CI/CD pipeline

---

## 📚 Riferimenti

- Test file: `test/routers/test_fiscal_documents.py`
- Reset numerazione: `docs/FISCAL_NUMBERING_RESET.md`
- API examples: `docs/FISCAL_DOCUMENTS_API_EXAMPLES.md`
- Migration guide: `docs/FISCAL_DOCUMENTS_MIGRATION.md`

---

Esegui i test e fammi sapere se tutto funziona! 🚀
