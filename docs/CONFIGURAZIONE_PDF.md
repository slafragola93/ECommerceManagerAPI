# Configurazione Generazione PDF Fatture

## Introduzione

Questo documento descrive come configurare il sistema per la generazione dei PDF delle fatture e note di credito.

## Configurazioni Necessarie

Le configurazioni sono memorizzate nella tabella `app_configurations` e possono essere gestite tramite l'API o direttamente nel database.

### Categoria: company_info

| Nome Configurazione | Descrizione | Esempio | Usato come |
|---------------------|-------------|---------|------------|
| `company_logo` | Path del logo aziendale | `media/logos/logo.png` | Logo nell'intestazione PDF |
| `company_name` | Ragione sociale | `Web Market s.r.l.` | Nome azienda |
| `address` | Indirizzo completo | `Corso Vittorio Emanuele, 110/5` | Indirizzo azienda |
| `city` | Città | `Napoli` | Città |
| `province` | Provincia | `NA` | Provincia |
| `postal_code` | CAP | `80121` | Codice postale |
| `vat_number` | Partita IVA | `IT08632861210` | P.IVA |
| `fiscal_code` | Codice Fiscale | `08632861210` | Codice Fiscale |
| `iban` | IBAN bancario | `IT79A0306939845100000014622` | IBAN |
| `bic_swift` | Codice BIC/SWIFT | `BCITITMM` | BIC |
| `pec` | PEC aziendale | `azienda@pec.it` | PEC |
| `sdi_code` | Codice SDI | `XXXXXXX` | Codice destinatario |

## Setup Iniziale

### 1. Inizializzare le Configurazioni

Esegui lo script di inizializzazione:

```bash
python scripts/init_app_configurations.py
```

Questo creerà tutte le configurazioni con valori vuoti.

### 2. Aggiornare le Configurazioni per PDF

Esegui lo script specifico per il PDF:

```bash
python scripts/update_pdf_configurations.py
```

Questo:
- Imposterà il path di default per `company_logo` a `media/logos/logo.png`
- Aggiungerà le configurazioni `pec` e `sdi_code` se mancanti
- Mostrerà la mappatura tra configurazioni DB e nomi usati nel codice

### 3. Caricare il Logo Aziendale

1. Posiziona il file del logo nella cartella `media/logos/`
2. Il nome file dovrebbe essere `logo.png` (o aggiorna la configurazione)
3. Formati supportati: PNG, JPG, JPEG
4. Dimensioni consigliate: larghezza 400px

Esempio:
```
media/
  └── logos/
      └── logo.png
```

### 4. Configurare i Dati Aziendali

Usa l'API per aggiornare le configurazioni:

```http
PUT /api/app_configurations/{id}
Content-Type: application/json

{
  "value": "Web Market s.r.l."
}
```

Oppure tramite interfaccia web se disponibile.

## Mappatura Configurazioni nel Codice

Il codice PDF usa i seguenti nomi per recuperare le configurazioni da `app_configuration`:

| Config DB (nome) | Variabile nel codice | Descrizione | Esempio |
|------------------|---------------------|-------------|---------|
| `company_name` | `company_name` | Ragione sociale | Web Market s.r.l. |
| `address` | `company_address` | Indirizzo | Corso Vittorio Emanuele ,110/5 |
| `postal_code` | `company_postal_code` | CAP | 80121 |
| `city` | `company_city` | Città | Napoli |
| `province` | `company_province` | Provincia | NA |
| - | `company_city_full` | Formato: CAP - Città (Prov) | 80121 - Napoli (NA) |
| `vat_number` | `company_vat` | Partita IVA | IT08632861210 |
| `fiscal_code` | `company_cf` | Codice Fiscale | 08632861210 |
| `iban` | `company_iban` | IBAN | IT79A... |
| `bic_swift` | `company_bic` | Codice BIC/SWIFT | BCITITMM |
| `pec` | `company_pec` | PEC | info@azienda.pec.it |
| `sdi_code` | `company_sdi` | Codice SDI | XXXXXXX |
| `company_logo` | `company_logo` | Path logo | media/logos/logo.png |

### Esempio codice:

```python
# Recupero da app_configuration
company_name = company_config.get('company_name', 'Web Market s.r.l.')
company_address = company_config.get('address', 'Corso Vittorio Emanuele ,110/5')
company_postal_code = company_config.get('postal_code', '80121')
company_city = company_config.get('city', 'Napoli')
company_province = company_config.get('province', 'NA')
company_city_full = f"{company_postal_code} - {company_city} ({company_province})"
company_vat = company_config.get('vat_number', 'IT08632861210')
company_cf = company_config.get('fiscal_code', '08632861210')
company_iban = company_config.get('iban', 'IT79A0306939845100000014622')
company_bic = company_config.get('bic_swift', 'BCITITMM')
company_pec = company_config.get('pec', '')
company_sdi = company_config.get('sdi_code', '')
```

## Struttura PDF Generato

Il PDF include:

### Header
- Logo aziendale (se configurato)
- Titolo documento (FATTURA o NOTA DI CREDITO)
- Numero e data documento

### Box Venditore
- Ragione sociale
- Indirizzo completo
- P.IVA e Codice Fiscale

### Box Cliente
- Nome/Ragione sociale cliente
- Indirizzo completo
- P.IVA (se disponibile)

### Dettagli Prodotti/Servizi
- Tabella con descrizione, quantità, prezzo unitario, sconto, totale
- Suddiviso per aliquote IVA

### Totali
- Imponibile per aliquota
- IVA per aliquota
- Totale documento

### Footer
- Dati bancari (IBAN, BIC)
- Note (se presenti)

## Troubleshooting

### Logo non visualizzato
- Verifica che il file esista nel path configurato
- Verifica i permessi di lettura del file
- Verifica che il formato sia supportato (PNG, JPG)

### Dati aziendali non corretti
- Verifica le configurazioni nella tabella `app_configurations`
- Assicurati che la categoria sia `company_info`
- Controlla che i valori non siano vuoti

### Errore generazione PDF
- Verifica che tutte le dipendenze siano installate: `fpdf`
- Controlla i log dell'applicazione per dettagli
- Verifica che la cartella `media/logos/` esista e sia accessibile

## API Endpoints

### Ottenere tutte le configurazioni
```http
GET /api/app_configurations?category=company_info
```

### Aggiornare una configurazione
```http
PUT /api/app_configurations/{id}
Content-Type: application/json

{
  "value": "nuovo_valore"
}
```

### Generare PDF fattura
```http
GET /api/fiscal_documents/{id}/pdf
```

## Note

- Le configurazioni possono essere modificate in qualsiasi momento
- Le modifiche si rifletteranno immediatamente sui nuovi PDF generati
- È consigliato fare un backup delle configurazioni prima di modifiche massive
- Il logo aziendale dovrebbe avere sfondo trasparente per migliore resa

## Esempio Configurazione Completa

```json
{
  "company_logo": "media/logos/logo.png",
  "company_name": "Web Market s.r.l.",
  "address": "Corso Vittorio Emanuele, 110/5",
  "postal_code": "80121",
  "city": "Napoli",
  "province": "NA",
  "vat_number": "IT08632861210",
  "fiscal_code": "08632861210",
  "iban": "IT79A0306939845100000014622",
  "bic_swift": "BCITITMM",
  "pec": "info@webmarket.pec.it",
  "sdi_code": "XXXXXXX"
}
```

