# 📚 Esempi API Fiscal Documents

## ⚠️ Come Usare gli Esempi in Swagger

Quando usi Swagger UI (`/docs`), **NON** copiare l'intera struttura con `"summary"` e `"value"`.

### **❌ SBAGLIATO:**
```json
{
  "summary": "Nota di credito totale",
  "value": {
    "id_invoice": 1,
    "reason": "Reso merce"
  }
}
```

### **✅ CORRETTO:**
```json
{
  "id_invoice": 1,
  "reason": "Reso merce",
  "is_partial": false,
  "is_electronic": true
}
```

---

## 📝 Esempi Corretti

### **1. Crea Fattura Elettronica**

**Endpoint:** `POST /api/v1/fiscal-documents/invoices`

**Payload:**
```json
{
  "id_order": 17,
  "is_electronic": true
}
```

**Response:**
```json
{
  "id_fiscal_document": 1,
  "document_type": "invoice",
  "tipo_documento_fe": "TD01",
  "id_order": 17,
  "document_number": "000001",
  "status": "pending",
  "is_electronic": true,
  "total_amount": 976.08,
  "date_add": "2025-09-30T12:00:00"
}
```

---

### **2. Genera XML**

**Endpoint:** `POST /api/v1/fiscal-documents/1/generate-xml`

**Payload:** (nessuno)

**Response:**
```json
{
  "id_fiscal_document": 1,
  "status": "generated",
  "filename": "IT01234567890_000001.xml",
  "xml_content": "<?xml version='1.0' encoding='UTF-8'?>..."
}
```

---

### **3. Crea Nota di Credito Totale**

**Endpoint:** `POST /api/v1/fiscal-documents/credit-notes`

**Payload:**
```json
{
  "id_invoice": 1,
  "reason": "Reso merce completo",
  "is_partial": false,
  "is_electronic": true
}
```

**Response:**
```json
{
  "id_fiscal_document": 2,
  "document_type": "credit_note",
  "tipo_documento_fe": "TD04",
  "id_order": 17,
  "id_fiscal_document_ref": 1,
  "document_number": "000001",
  "status": "pending",
  "is_electronic": true,
  "credit_note_reason": "Reso merce completo",
  "is_partial": false,
  "total_amount": 976.08
}
```

---

### **4. Crea Nota di Credito Parziale**

**Endpoint:** `POST /api/v1/fiscal-documents/credit-notes`

**Payload:**
```json
{
  "id_invoice": 1,
  "reason": "Reso parziale - articolo difettoso",
  "is_partial": true,
  "is_electronic": true,
  "items": [
    {
      "id_order_detail": 15,
      "quantity": 1,
      "unit_price": 465.099
    }
  ]
}
```

**Response:**
```json
{
  "id_fiscal_document": 3,
  "document_type": "credit_note",
  "tipo_documento_fe": "TD04",
  "id_order": 17,
  "id_fiscal_document_ref": 1,
  "document_number": "000002",
  "status": "pending",
  "is_electronic": true,
  "credit_note_reason": "Reso parziale - articolo difettoso",
  "is_partial": true,
  "total_amount": 465.099,
  "details": [
    {
      "id_fiscal_document_detail": 1,
      "id_fiscal_document": 3,
      "id_order_detail": 15,
      "quantity": 1.0,
      "unit_price": 465.099,
      "total_amount": 465.099
    }
  ]
}
```

---

### **5. Invia a FatturaPA (solo upload)**

**Endpoint:** `POST /api/v1/fiscal-documents/1/send-to-sdi`

**Payload:**
```json
{
  "send_to_sdi": false
}
```

**Response:**
```json
{
  "id_fiscal_document": 1,
  "status": "uploaded",
  "upload_result": "{\"name\":\"...\",\"url\":\"...\"}"
}
```

---

### **6. Invia a SDI (upload + invio)**

**Endpoint:** `POST /api/v1/fiscal-documents/1/send-to-sdi`

**Payload:**
```json
{
  "send_to_sdi": true
}
```

**Response:**
```json
{
  "id_fiscal_document": 1,
  "status": "sent",
  "upload_result": "{\"sdi_id\":\"12345\",\"timestamp\":\"2025-09-30T12:00:00\"}"
}
```

---

### **7. Lista Fatture per Ordine**

**Endpoint:** `GET /api/v1/fiscal-documents/invoices/order/17`

**Response:**
```json
[
  {
    "id_fiscal_document": 1,
    "document_type": "invoice",
    "document_number": "000001",
    "status": "sent",
    "total_amount": 976.08
  },
  {
    "id_fiscal_document": 4,
    "document_type": "invoice",
    "document_number": "000045",
    "status": "pending",
    "total_amount": 250.00
  }
]
```

---

### **8. Note di Credito per Fattura**

**Endpoint:** `GET /api/v1/fiscal-documents/credit-notes/invoice/1`

**Response:**
```json
[
  {
    "id_fiscal_document": 2,
    "document_type": "credit_note",
    "credit_note_reason": "Reso totale",
    "is_partial": false,
    "total_amount": 976.08
  },
  {
    "id_fiscal_document": 3,
    "document_type": "credit_note",
    "credit_note_reason": "Reso parziale",
    "is_partial": true,
    "total_amount": 465.099,
    "details": [...]
  }
]
```

---

## 🔍 Validazioni Errori Comuni

### **Errore 1: OrderDetail non in fattura**
```json
{
  "id_invoice": 1,
  "is_partial": true,
  "items": [
    {"id_order_detail": 999, "quantity": 1, "unit_price": 100}
  ]
}

// ❌ Response:
{
  "detail": "OrderDetail 999 non presente nella fattura 1"
}
```

### **Errore 2: Quantità eccessiva**
```json
{
  "id_invoice": 1,
  "is_partial": true,
  "items": [
    {"id_order_detail": 15, "quantity": 10, "unit_price": 465}
  ]
}

// ❌ Response (se fattura ha qty=3):
{
  "detail": "Quantità da stornare (10) superiore a quella fatturata (3)"
}
```

### **Errore 3: Fattura non elettronica**
```json
{
  "id_order": 99,
  "is_electronic": true
}

// ❌ Response (se ordine ha indirizzo estero):
{
  "detail": "La fattura elettronica può essere emessa solo per indirizzi italiani"
}
```

---

## 📋 Workflow Completo

```bash
# 1. Crea fattura
POST /fiscal-documents/invoices
{"id_order": 17, "is_electronic": true}
→ id_fiscal_document: 1

# 2. Genera XML
POST /fiscal-documents/1/generate-xml
→ status: "generated"

# 3. Invia a FatturaPA
POST /fiscal-documents/1/send-to-sdi
{"send_to_sdi": false}
→ status: "uploaded"

# 4. (Se serve) Crea nota credito
POST /fiscal-documents/credit-notes
{
  "id_invoice": 1,
  "reason": "Reso parziale",
  "is_partial": true,
  "items": [{"id_order_detail": 15, "quantity": 1, "unit_price": 465.099}]
}
→ id_fiscal_document: 2

# 5. Genera XML nota credito
POST /fiscal-documents/2/generate-xml
→ status: "generated"

# 6. Invia nota credito
POST /fiscal-documents/2/send-to-sdi
{"send_to_sdi": true}
→ status: "sent"
```

---

## 💡 Tips

1. **In Swagger**: Seleziona l'esempio dal dropdown, poi clicca "Try it out" e modifica solo i valori necessari
2. **id_invoice**: È l'`id_fiscal_document` di una fattura, non confondere con `id_order`
3. **Quantità**: Per note parziali, deve essere ≤ quantità fatturata
4. **Validazioni**: Tutti gli errori hanno messaggi chiari in italiano

---

Usa questo documento come riferimento! 📖
