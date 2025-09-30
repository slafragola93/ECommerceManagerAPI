# 📄 Migrazione Sistema Documenti Fiscali

## 🔄 Migrazione da `invoices` a `fiscal_documents`

Il sistema di gestione fatture è stato completamente ridisegnato per supportare **fatture** e **note di credito** in un'unica tabella unificata.

---

## 📊 Struttura Database

### **Prima (Deprecato):**
```
invoices
├── id_invoice
├── id_order
├── document_number
├── filename
├── xml_content
├── status
└── ...
```

### **Dopo (Nuovo):**
```
fiscal_documents
├── id_fiscal_document
├── document_type ('invoice' | 'credit_note')
├── tipo_documento_fe ('TD01' | 'TD04' | ...)
├── id_order
├── id_fiscal_document_ref (per note di credito)
├── document_number (sequenziale per elettronici)
├── internal_number (numero interno alternativo)
├── is_electronic (boolean)
├── is_partial (per note di credito parziali)
├── credit_note_reason (motivo nota credito)
└── ...

fiscal_document_details (per note parziali)
├── id_fiscal_document_detail
├── id_fiscal_document
├── id_order_detail
├── quantity (quantità da stornare)
├── unit_price
└── total_amount
```

---

## 🚀 Migrazione Automatica

La migrazione dei dati esistenti è **automatica** tramite Alembic:

```bash
alembic upgrade head
```

### Operazioni eseguite:
1. ✅ Rinomina `invoices` → `fiscal_documents`
2. ✅ Rinomina `id_invoice` → `id_fiscal_document`
3. ✅ Aggiunge nuove colonne
4. ✅ Popola `document_type='invoice'` per tutti i record esistenti
5. ✅ Popola `tipo_documento_fe='TD01'` per fatture elettroniche esistenti
6. ✅ Popola `is_electronic` basandosi su `xml_content`
7. ✅ Crea indici e foreign keys

---

## 📝 Nuovi Endpoint API

### **Vecchi Endpoint (Deprecati):**
- `POST /api/v1/invoices` ❌
- `GET /api/v1/invoices/{id}` ❌

### **Nuovi Endpoint (Usare questi):**

#### **Fatture:**
```bash
# Crea fattura
POST /api/v1/fiscal-documents/invoices
{
  "id_order": 12345,
  "is_electronic": true  # Solo per IT
}

# Tutte le fatture per ordine (può averne multiple)
GET /api/v1/fiscal-documents/invoices/order/{id_order}
```

#### **Note di Credito:**
```bash
# Crea nota di credito totale
POST /api/v1/fiscal-documents/credit-notes
{
  "id_invoice": 123,
  "reason": "Reso merce",
  "is_partial": false,
  "is_electronic": true
}

# Crea nota di credito parziale
POST /api/v1/fiscal-documents/credit-notes
{
  "id_invoice": 123,
  "reason": "Reso parziale",
  "is_partial": true,
  "is_electronic": true,
  "items": [
    {
      "id_order_detail": 456,
      "quantity": 2.0,
      "unit_price": 50.00
    }
  ]
}

# Note di credito per fattura
GET /api/v1/fiscal-documents/credit-notes/invoice/{id_invoice}
```

#### **Operazioni Generiche:**
```bash
# Documento per ID
GET /api/v1/fiscal-documents/{id_fiscal_document}

# Lista con filtri
GET /api/v1/fiscal-documents?document_type=invoice&is_electronic=true

# Genera XML
POST /api/v1/fiscal-documents/{id_fiscal_document}/generate-xml

# Aggiorna status
PATCH /api/v1/fiscal-documents/{id_fiscal_document}/status

# Elimina (solo pending)
DELETE /api/v1/fiscal-documents/{id_fiscal_document}
```

---

## 🔧 Regole di Business

### **Fatture:**
1. ✅ Un ordine può avere **multiple fatture** (es. fattura iniziale + integrazioni)
2. ✅ Fatture elettroniche **SOLO per indirizzi italiani** (id_country=1)
3. ✅ Numerazione sequenziale automatica per elettroniche
4. ✅ Tipo documento FatturaPA: **TD01**

### **Note di Credito:**
1. ✅ Richiedono fattura esistente (id_fiscal_document_ref)
2. ✅ Elettroniche SOLO se fattura è elettronica
3. ✅ Supporto **totali** (tutto) e **parziali** (alcuni articoli)
4. ✅ Tipo documento FatturaPA: **TD04**
5. ✅ Quantità **negative** per storno nell'XML

---

## 📦 Codice Esempio

### **Repository Pattern:**
```python
from src.repository.fiscal_document_repository import FiscalDocumentRepository

repo = FiscalDocumentRepository(db)

# Crea fattura
invoice = repo.create_invoice(
    id_order=12345,
    is_electronic=True
)

# Crea nota credito totale
credit_note = repo.create_credit_note(
    id_invoice=invoice.id_fiscal_document,
    reason="Reso merce",
    is_partial=False,
    is_electronic=True
)

# Crea nota credito parziale
partial_credit = repo.create_credit_note(
    id_invoice=invoice.id_fiscal_document,
    reason="Reso parziale",
    is_partial=True,
    items=[
        {
            'id_order_detail': 456,
            'quantity': 2.0,
            'unit_price': 50.00
        }
    ],
    is_electronic=True
)
```

### **Genera XML:**
```python
from src.services.fatturapa_service import FatturaPAService

service = FatturaPAService(db)

# Genera XML (supporta TD01 e TD04)
result = service.generate_xml_from_fiscal_document(id_fiscal_document)

if result['status'] == 'success':
    filename = result['filename']
    xml_content = result['xml_content']
    
    # Salva XML
    repo.update_fiscal_document_xml(
        id_fiscal_document=id_fiscal_document,
        filename=filename,
        xml_content=xml_content
    )
```

---

## 🔍 Query Esempi

### **Recupera fatture elettroniche:**
```python
invoices = repo.get_fiscal_documents(
    document_type='invoice',
    is_electronic=True,
    status='sent'
)
```

### **Recupera note di credito di una fattura:**
```python
credit_notes = repo.get_credit_notes_by_invoice(id_invoice=123)
```

### **Verifica fatture di un ordine:**
```python
# Tutte le fatture
invoices = repo.get_invoices_by_order(id_order=12345)
for invoice in invoices:
    print(f"Fattura {invoice.id_fiscal_document}: {invoice.status}")

# Solo la prima (deprecato)
invoice = repo.get_invoice_by_order(id_order=12345)
if invoice:
    print(f"Prima fattura: {invoice.id_fiscal_document}")
```

---

## ⚠️ Breaking Changes

### **Modello `Invoice` (Deprecato):**
- ❌ La tabella `invoices` non esiste più
- ❌ Usare `FiscalDocument` invece
- ❌ `InvoiceRepository` è deprecato
- ✅ Usare `FiscalDocumentRepository`

### **Relationship in `Order`:**
```python
# Prima (deprecato):
order.invoices  # ❌

# Dopo (nuovo):
order.fiscal_documents  # ✅
```

---

## 📚 Tipi Documento FatturaPA Supportati

| Codice | Descrizione | Implementato |
|--------|-------------|--------------|
| TD01 | Fattura | ✅ |
| TD04 | Nota di credito | ✅ |
| TD05 | Nota di debito | ⏳ Futuro |
| TD06 | Parcella | ⏳ Futuro |

---

## 🧪 Testing

### **Crea Fixtures:**
```bash
python scripts/create_fixtures.py
```

Le fixtures ora creano:
- ✅ Fatture elettroniche (solo per IT)
- ✅ Fatture non elettroniche
- ✅ Note di credito totali
- ✅ Note di credito parziali

---

## 🔐 Validazioni

### **Fatture Elettroniche:**
1. ✅ Indirizzo fatturazione **DEVE essere italiano** (id_country=1)
2. ✅ Deve avere PEC o Codice Destinatario
3. ✅ Numerazione sequenziale automatica
4. ✅ XML conforme FatturaPA

### **Note di Credito:**
1. ✅ Fattura di riferimento **DEVE esistere**
2. ✅ Se elettronica, fattura DEVE essere elettronica
3. ✅ Se parziale, items DEVONO essere specificati
4. ✅ Quantità articoli ≤ quantità originali

---

## 📞 Support

Per domande o problemi:
1. Consulta la documentazione API in `/docs`
2. Verifica esempi in `docs/examples/`
3. Controlla test in `test/routers/test_fiscal_documents.py`

---

## 🎯 Roadmap

- ✅ Fatture (TD01)
- ✅ Note di credito totali (TD04)
- ✅ Note di credito parziali (TD04)
- ⏳ Note di debito (TD05)
- ⏳ Parcelle (TD06)
- ⏳ Upload automatico SDI
- ⏳ Gestione ricevute SDI
