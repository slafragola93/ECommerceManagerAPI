# 🔢 Reset Numerazione Fatture - Guida Implementazione

## 📋 Requisito

La numerazione delle fatture elettroniche deve **resettarsi a 000001** ogni **1 gennaio**.

---

## ⚠️ Situazione Attuale

**Comportamento corrente:**
```python
def _get_next_electronic_number(self, doc_type: str) -> str:
    # Recupera ULTIMO numero, indipendentemente dall'anno
    last_doc = self.db.query(FiscalDocument).filter(
        document_type == doc_type,
        is_electronic == True,
        document_number.isnot(None)
    ).order_by(desc(id_fiscal_document)).first()
    
    if last_doc:
        next_number = int(last_doc.document_number) + 1
    else:
        next_number = 1
    
    return f"{next_number:06d}"
```

**Problema:**
- 31 dicembre 2024: Fattura #000099
- 1 gennaio 2025: Fattura #000100 ❌ (dovrebbe essere #000001)

---

## ✅ Soluzione Proposta

### **Opzione A: Reset Automatico con Query Filtrata per Anno**

Modifica `_get_next_electronic_number` per considerare solo l'anno corrente:

```python
def _get_next_electronic_number(self, doc_type: str) -> str:
    """
    Genera numero sequenziale per anno corrente
    La numerazione resetta automaticamente ogni 1 gennaio
    """
    from datetime import datetime
    from sqlalchemy import extract, func
    
    current_year = datetime.now().year
    
    # Recupera ultimo numero dell'ANNO CORRENTE
    last_doc = self.db.query(FiscalDocument).filter(
        FiscalDocument.document_type == doc_type,
        FiscalDocument.is_electronic == True,
        FiscalDocument.document_number.isnot(None),
        extract('year', FiscalDocument.date_add) == current_year  # ✅ Solo anno corrente
    ).order_by(desc(FiscalDocument.id_fiscal_document)).first()
    
    if last_doc and last_doc.document_number:
        try:
            last_number = int(last_doc.document_number)
            next_number = last_number + 1
        except ValueError:
            next_number = 1
    else:
        # Primo documento dell'anno
        next_number = 1
    
    return f"{next_number:06d}"
```

**Vantaggi:**
- ✅ Reset automatico ogni anno
- ✅ No job schedulati
- ✅ Semplice da implementare
- ✅ Funziona anche con database vuoto

**Comportamento:**
- 31 dicembre 2024: Fattura #000099
- 1 gennaio 2025: Fattura #000001 ✅ (reset automatico)

---

### **Opzione B: Job Schedulato (Più Complesso)**

Usa un job schedulato che resetta un contatore:

#### **1. Aggiungi tabella contatori:**
```sql
CREATE TABLE fiscal_counters (
    id INT PRIMARY KEY AUTO_INCREMENT,
    year INT NOT NULL,
    document_type VARCHAR(20) NOT NULL,
    last_number INT DEFAULT 0,
    UNIQUE KEY(year, document_type)
);
```

#### **2. Modello:**
```python
class FiscalCounter(Base):
    __tablename__ = "fiscal_counters"
    
    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False)
    document_type = Column(String(20), nullable=False)
    last_number = Column(Integer, default=0)
```

#### **3. Metodo aggiornato:**
```python
def _get_next_electronic_number(self, doc_type: str) -> str:
    current_year = datetime.now().year
    
    # Recupera contatore anno corrente
    counter = self.db.query(FiscalCounter).filter(
        FiscalCounter.year == current_year,
        FiscalCounter.document_type == doc_type
    ).first()
    
    if not counter:
        # Primo documento dell'anno - crea contatore
        counter = FiscalCounter(
            year=current_year,
            document_type=doc_type,
            last_number=1
        )
        self.db.add(counter)
    else:
        # Incrementa contatore
        counter.last_number += 1
    
    self.db.commit()
    return f"{counter.last_number:06d}"
```

#### **4. Job schedulato (opzionale):**
```python
# Cron job che gira ogni 1 gennaio alle 00:00
@scheduler.scheduled_job('cron', month=1, day=1, hour=0, minute=0)
def reset_fiscal_counters():
    """Reset contatori fiscali ogni anno"""
    # I contatori si creano automaticamente quando serve
    # Questo job è solo per logging
    logger.info(f"Nuovo anno fiscale: {datetime.now().year}")
```

**Vantaggi:**
- ✅ Contatori dedicati
- ✅ Performance migliore (no query su FiscalDocument)
- ✅ Audit trail completo

**Svantaggi:**
- ❌ Più complesso
- ❌ Richiede tabella aggiuntiva
- ❌ Migration necessaria

---

## 🎯 Raccomandazione: **Opzione A**

**Perché:**
1. Più semplice da implementare
2. No tabelle aggiuntive
3. No job schedulati
4. Reset automatico basato su query
5. Già funzionante con struttura attuale

---

## 🔧 Implementazione Opzione A

### **File da Modificare:**

**`src/repository/fiscal_document_repository.py`:**

```python
from sqlalchemy import extract

def _get_next_electronic_number(self, doc_type: str) -> str:
    """
    Genera il prossimo numero sequenziale per documenti elettronici
    La numerazione resetta automaticamente ogni anno (1 gennaio)
    
    Args:
        doc_type: 'invoice' o 'credit_note'
    
    Returns:
        Numero sequenziale come stringa (es. "000001")
    """
    from datetime import datetime
    
    current_year = datetime.now().year
    
    # Recupera l'ultimo numero dell'ANNO CORRENTE per questo tipo
    last_doc = self.db.query(FiscalDocument).filter(
        and_(
            FiscalDocument.document_type == doc_type,
            FiscalDocument.is_electronic == True,
            FiscalDocument.document_number.isnot(None),
            extract('year', FiscalDocument.date_add) == current_year  # ✅ Filtro per anno
        )
    ).order_by(desc(FiscalDocument.id_fiscal_document)).first()
    
    if last_doc and last_doc.document_number:
        try:
            last_number = int(last_doc.document_number)
            next_number = last_number + 1
        except ValueError:
            next_number = 1
    else:
        # Primo documento dell'anno
        next_number = 1
    
    return f"{next_number:06d}"
```

---

## 🧪 Test per Verificare

```python
def test_numbering_resets_new_year():
    """Verifica reset numerazione a inizio anno"""
    
    # Simula fatture 2024
    invoice_2024 = FiscalDocument(
        document_type='invoice',
        document_number='000099',
        date_add=datetime(2024, 12, 31)
    )
    db.add(invoice_2024)
    db.commit()
    
    # Simula nuova fattura 2025
    repo = FiscalDocumentRepository(db)
    
    # Mock datetime.now() per restituire 2025
    with patch('datetime.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 1, 1)
        
        next_number = repo._get_next_electronic_number('invoice')
        
        assert next_number == '000001'  # ✅ Reset!
```

---

## 📅 Timeline Numerazione

```
Anno 2024:
├── 01/01/2024: Fattura #000001
├── 15/03/2024: Fattura #000002
├── ...
└── 31/12/2024: Fattura #000099

Anno 2025 (RESET):
├── 01/01/2025: Fattura #000001  ✅ Reset
├── 10/01/2025: Fattura #000002
├── ...
```

---

## ⚙️ Configurazione Aggiuntiva (Opzionale)

Se vuoi logging del reset:

```python
def _get_next_electronic_number(self, doc_type: str) -> str:
    current_year = datetime.now().year
    
    # ... query ...
    
    if not last_doc:
        # Primo documento dell'anno - log reset
        logger.info(f"🔄 Reset numerazione {doc_type} per anno {current_year}")
    
    return f"{next_number:06d}"
```

---

## ✅ Conclusione

**Raccomando Opzione A** perché:
- Semplice
- Automatica
- No infrastruttura aggiuntiva
- Conforme normativa fiscale

Vuoi che implementi subito l'Opzione A? 🚀
