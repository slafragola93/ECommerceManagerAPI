# Carrier Configuration Select Options

Questo documento contiene tutte le opzioni valide per i campi select delle configurazioni dei corrieri.

## BRT Configuration Select Options

### collection_mode_options
```json
{
  "value": "contanti",
  "label": "Contanti"
}
```
Opzioni disponibili:
- `contanti` - Contanti
- `assegno` - Assegno
- `bonifico` - Bonifico bancario
- `carta_credito` - Carta di credito

### network_options
```json
{
  "value": "nazionale",
  "label": "Nazionale"
}
```
Opzioni disponibili:
- `nazionale` - Nazionale
- `internazionale` - Internazionale
- `europeo` - Europeo

### label_format_options
```json
{
  "value": "pdf",
  "label": "PDF"
}
```
Opzioni disponibili:
- `pdf` - PDF
- `zpl` - ZPL (Zebra Programming Language)
- `epl` - EPL (Eltron Programming Language)

### customer_notification_options
```json
{
  "value": "email",
  "label": "Email"
}
```
Opzioni disponibili:
- `email` - Email
- `sms` - SMS
- `entrambi` - Email e SMS
- `nessuno` - Nessuna notifica

### tracking_type_options
```json
{
  "value": "standard",
  "label": "Standard"
}
```
Opzioni disponibili:
- `standard` - Standard
- `premium` - Premium
- `express` - Express

## Fedex Configuration Select Options

### sandbox_options
```json
{
  "value": "true",
  "label": "Sandbox (Test)"
}
```
Opzioni disponibili:
- `true` - Sandbox (Test)
- `false` - Produzione

### service_type_options
```json
{
  "value": "FEDEX_GROUND",
  "label": "FedEx Ground"
}
```
Opzioni disponibili:
- `FEDEX_GROUND` - FedEx Ground
- `FEDEX_EXPRESS_SAVER` - FedEx Express Saver
- `FEDEX_2_DAY` - FedEx 2Day
- `FEDEX_2_DAY_AM` - FedEx 2Day A.M.
- `FEDEX_STANDARD_OVERNIGHT` - FedEx Standard Overnight
- `FEDEX_PRIORITY_OVERNIGHT` - FedEx Priority Overnight
- `FEDEX_FIRST_OVERNIGHT` - FedEx First Overnight

### packaging_type_options
```json
{
  "value": "YOUR_PACKAGING",
  "label": "Your Packaging"
}
```
Opzioni disponibili:
- `YOUR_PACKAGING` - Your Packaging
- `FEDEX_BOX` - FedEx Box
- `FEDEX_PAK` - FedEx Pak
- `FEDEX_TUBE` - FedEx Tube
- `FEDEX_ENVELOPE` - FedEx Envelope

### pickup_type_options
```json
{
  "value": "USE_SCHEDULED_PICKUP",
  "label": "Use Scheduled Pickup"
}
```
Opzioni disponibili:
- `USE_SCHEDULED_PICKUP` - Use Scheduled Pickup
- `USE_SCHEDULED_PICKUP` - Use Scheduled Pickup
- `USE_SCHEDULED_PICKUP` - Use Scheduled Pickup

### customs_charges_options
```json
{
  "value": "SENDER",
  "label": "Sender"
}
```
Opzioni disponibili:
- `SENDER` - Sender
- `RECIPIENT` - Recipient
- `THIRD_PARTY` - Third Party

### format_options
```json
{
  "value": "PDF",
  "label": "PDF"
}
```
Opzioni disponibili:
- `PDF` - PDF
- `PNG` - PNG
- `EPL2` - EPL2
- `ZPLII` - ZPLII

### notes_field_options
```json
{
  "value": "1",
  "label": "Abilitato"
}
```
Opzioni disponibili:
- `1` - Abilitato
- `0` - Disabilitato

## DHL Configuration Select Options

### layout_options
```json
{
  "value": "A4",
  "label": "A4"
}
```
Opzioni disponibili:
- `A4` - A4
- `A5` - A5
- `A6` - A6
- `LETTER` - Letter

### cash_on_delivery_options
```json
{
  "value": "N",
  "label": "No"
}
```
Opzioni disponibili:
- `N` - No
- `Y` - Yes

### print_waybill_options
```json
{
  "value": "1",
  "label": "Sì"
}
```
Opzioni disponibili:
- `1` - Sì
- `0` - No

### sku_quantity_options
```json
{
  "value": "1",
  "label": "Abilitato"
}
```
Opzioni disponibili:
- `1` - Abilitato
- `0` - Disabilitato

### national_service_options
```json
{
  "value": "DHL_EXPRESS",
  "label": "DHL Express"
}
```
Opzioni disponibili:
- `DHL_EXPRESS` - DHL Express
- `DHL_EXPRESS_12` - DHL Express 12:00
- `DHL_EXPRESS_10` - DHL Express 10:00
- `DHL_EXPRESS_9` - DHL Express 9:00

### international_service_options
```json
{
  "value": "DHL_EXPRESS_WORLDWIDE",
  "label": "DHL Express Worldwide"
}
```
Opzioni disponibili:
- `DHL_EXPRESS_WORLDWIDE` - DHL Express Worldwide
- `DHL_EXPRESS_12` - DHL Express 12:00
- `DHL_EXPRESS_10` - DHL Express 10:00
- `DHL_EXPRESS_9` - DHL Express 9:00
- `DHL_EXPRESS_EARLY` - DHL Express Early

## Note Implementative

1. **Struttura JSON**: Tutti i campi select devono essere salvati come JSON con la struttura `{"value": "...", "label": "..."}`

2. **Validazione**: I valori devono essere validati lato client e server per garantire che solo opzioni valide vengano salvate

3. **Internazionalizzazione**: I label possono essere tradotti in base alla lingua dell'utente

4. **Aggiornamenti**: Le opzioni possono essere aggiornate dinamicamente tramite endpoint di configurazione

5. **Fallback**: In caso di valori non validi, utilizzare il primo valore della lista come default
