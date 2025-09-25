# Correzioni Namespace e CodiceDestinatario FatturaPA

## Correzioni Implementate

### 1. **Namespace con Prefisso `p:`**

#### **Prima (ERRORE)**
```xml
<FatturaElettronica xmlns="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2">
  <FatturaElettronicaHeader>
    <DatiTrasmissione>
      <CodiceDestinatario>1234567</CodiceDestinatario>
    </DatiTrasmissione>
  </FatturaElettronicaHeader>
</FatturaElettronica>
```

#### **Ora (CORRETTO)**
```xml
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2">
  <p:FatturaElettronicaHeader>
    <p:DatiTrasmissione>
      <p:CodiceDestinatario>1234567</p:CodiceDestinatario>
    </p:DatiTrasmissione>
  </p:FatturaElettronicaHeader>
</p:FatturaElettronica>
```

### 2. **Logica CodiceDestinatario per FormatoTrasmissione**

#### **FPR12 (Fatture verso Privati)**
- **7 caratteri**: Codice SDI del destinatario
- **Default**: `0000000` se non accreditato

```python
if formato_trasmissione == "FPR12":
    if customer_sdi and len(customer_sdi) == 7:
        codice_destinatario = customer_sdi
    else:
        codice_destinatario = "0000000"  # Non accreditato
```

#### **FPA12 (Fatture verso PA)**
- **6 caratteri**: Codice ufficio destinatario PA
- **Errore**: Se non rispetta la lunghezza

```python
elif formato_trasmissione == "FPA12":
    if customer_sdi and len(customer_sdi) == 6:
        codice_destinatario = customer_sdi
    else:
        raise ValueError("Per FPA12 CodiceDestinatario deve essere esattamente 6 caratteri")
```

#### **Operazioni Transfrontaliere**
- **7 caratteri**: `XXXXXXX`

```python
else:
    codice_destinatario = "XXXXXXX"  # Transfrontaliere
```

## Implementazione Tecnica

### **Funzione Helper per Prefisso `p:`**
```python
def _create_element(self, parent, tag: str, text: str = None, **attrs) -> ET.Element:
    """Helper per creare elementi con prefisso p:"""
    element = ET.SubElement(parent, f"p:{tag}")
    if text:
        element.text = text
    for key, value in attrs.items():
        element.set(key, value)
    return element
```

### **Root Element Corretto**
```python
# Crea root element con prefisso p:
root = ET.Element("p:FatturaElettronica")
root.set("versione", "FPR12")
root.set("xmlns:p", "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2")
root.set("xmlns:ds", "http://www.w3.org/2000/09/xmldsig#")
root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
```

### **Tutti gli Elementi con Prefisso `p:`**
```python
# Prima
ET.SubElement(dati_trasmissione, "CodiceDestinatario").text = codice_destinatario

# Ora
self._create_element(dati_trasmissione, "CodiceDestinatario", codice_destinatario)
```

## Esempi di Utilizzo

### **Fattura verso Privato (FPR12)**
```json
{
  "formato_trasmissione": "FPR12",
  "customer_sdi": "1234567",
  "codice_destinatario": "1234567"
}
```

### **Fattura verso Privato senza SDI (FPR12)**
```json
{
  "formato_trasmissione": "FPR12", 
  "customer_sdi": null,
  "codice_destinatario": "0000000"
}
```

### **Fattura verso PA (FPA12)**
```json
{
  "formato_trasmissione": "FPA12",
  "customer_sdi": "123456",
  "codice_destinatario": "123456"
}
```

### **Operazione Transfrontaliera**
```json
{
  "formato_trasmissione": "TRANSFRONTALIERA",
  "codice_destinatario": "XXXXXXX"
}
```

## Validazioni Implementate

### **CodiceDestinatario FPR12**
```python
if formato_trasmissione == "FPR12":
    if customer_sdi and len(customer_sdi) == 7:
        # Usa codice SDI
        codice_destinatario = customer_sdi
    else:
        # Default per non accreditati
        codice_destinatario = "0000000"
```

### **CodiceDestinatario FPA12**
```python
elif formato_trasmissione == "FPA12":
    if customer_sdi and len(customer_sdi) == 6:
        # Usa codice PA
        codice_destinatario = customer_sdi
    else:
        # Errore se non rispetta lunghezza
        raise ValueError("Per FPA12 CodiceDestinatario deve essere esattamente 6 caratteri")
```

## Debug e Logging

### **Log di Esempio**
```
=== VALIDAZIONE CODICE DESTINATARIO ===
FormatoTrasmissione: FPR12
CodiceDestinatario da SDI: '1234567'
✅ CodiceDestinatario validato: 1234567
```

### **Log per Non Accreditato**
```
=== VALIDAZIONE CODICE DESTINATARIO ===
FormatoTrasmissione: FPR12
CodiceDestinatario default (non accreditato): '0000000'
✅ CodiceDestinatario validato: 0000000
```

### **Log per PA**
```
=== VALIDAZIONE CODICE DESTINATARIO ===
FormatoTrasmissione: FPA12
CodiceDestinatario PA: '123456'
✅ CodiceDestinatario validato: 123456
```

## Risultato XML

### **XML Generato Corretto**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2" 
                      xmlns:ds="http://www.w3.org/2000/09/xmldsig#" 
                      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
                      versione="FPR12">
  <p:FatturaElettronicaHeader>
    <p:DatiTrasmissione>
      <p:IdTrasmittente>
        <p:IdPaese>IT</p:IdPaese>
        <p:IdCodice>12345678901</p:IdCodice>
      </p:IdTrasmittente>
      <p:ProgressivoInvio>00001</p:ProgressivoInvio>
      <p:FormatoTrasmissione>FPR12</p:FormatoTrasmissione>
      <p:CodiceDestinatario>1234567</p:CodiceDestinatario>
    </p:DatiTrasmissione>
    <!-- ... resto della struttura ... -->
  </p:FatturaElettronicaHeader>
  <p:FatturaElettronicaBody>
    <!-- ... contenuto fattura ... -->
  </p:FatturaElettronicaBody>
</p:FatturaElettronica>
```

## Benefici delle Correzioni

1. **✅ Namespace Corretto**: Tutti gli elementi ora hanno il prefisso `p:` richiesto
2. **✅ CodiceDestinatario Intelligente**: Logica basata su FormatoTrasmissione
3. **✅ Gestione Errori**: Validazioni specifiche per ogni tipo
4. **✅ Debug Dettagliato**: Logging completo per troubleshooting
5. **✅ Compatibilità SdI**: Rispetta le specifiche FatturaPA ufficiali

## Test

### **Test FPR12 con SDI**
```bash
GET /fatturapa/orders/36/xml-only
# Dovrebbe generare XML con CodiceDestinatario = customer_sdi
```

### **Test FPR12 senza SDI**
```bash
GET /fatturapa/orders/36/xml-only
# Dovrebbe generare XML con CodiceDestinatario = "0000000"
```

### **Test FPA12**
```bash
# Modifica formato_trasmissione a "FPA12" nel codice
# Dovrebbe validare CodiceDestinatario a 6 caratteri
```

### **Debug Step-by-Step**
```bash
GET /fatturapa/orders/36/debug-xml-generation
# Mostra tutti i passaggi della generazione XML
```

