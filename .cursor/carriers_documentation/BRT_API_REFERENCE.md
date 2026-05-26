# BRT — Riferimento Tecnico API REST

> Generato dalla documentazione ufficiale "RestShipmentProd v.00" (Maggio 2022)
> Fonte: file `SwaggerViewerShipment.json` + HTML estratti
> Aggiornato: 2026-05-13

---

## 📑 Indice

1. [Overview](#1-overview)
2. [Autenticazione](#2-autenticazione)
3. [Endpoint Shipments API](#3-endpoint-shipments-api)
4. [Schema `createData` — Lunghezze massime](#4-schema-createdata--lunghezze-massime)
5. [Schema `createData` — Campi obbligatori](#5-schema-createdata--campi-obbligatori)
6. [Catalogo codici errore](#6-catalogo-codici-errore)
7. [Regole di pre-validazione raccomandate](#7-regole-di-pre-validazione-raccomandate)
8. [Mapping con il dominio Elettronew](#8-mapping-con-il-dominio-elettronew)

---

## 1. Overview

**Base URL produzione:** `https://api.brt.it/rest/v1/shipments`

**Categorie di endpoint:**
- **Shipments API** — creazione/conferma/cancellazione spedizioni e calcolo routing
- **Tracking API** — (non oggetto di questo riferimento, separato)

**Protocollo:** REST/HTTPS, body JSON.

**Note di ambiente:**
- Lo Swagger interno cita `host: as777:10061` con `basePath: /rest/v1/shipments` — quello è infrastruttura interna BRT. Per i client esterni si usa **sempre** `https://api.brt.it/rest/v1/shipments`.

---

## 2. Autenticazione

Schema `account` (presente in ogni request):

| Campo | Tipo | Max | Note |
|---|---|---|---|
| `userID` | string | 35 | Codice utente fornito da BRT |
| `password` | string | 35 | Password fornita da BRT |

⚠️ L'`account` viene inviato nel **body** della request, non in header. Il valore di `senderCustomerCode` in `createData` deve essere collegato a `account.userID` (altrimenti errore `-67`).

---

## 3. Endpoint Shipments API

| Metodo | Path | Scopo |
|---|---|---|
| `POST` | `/shipment` | Crea una nuova spedizione (request: `createRequest`, response: `createResult` → `createResponse`) |
| `PUT` | `/shipment` | Conferma (presa in carico) una spedizione precedentemente calcolata |
| `PUT` | `/routing` | Calcola routing senza creare la spedizione (test di fattibilità) |
| `PUT` | `/delete` | Cancella una spedizione |

### 3.1 Struttura `createRequest` (POST /shipment)

```
createRequest
├── account              → credenziali (userID, password)
├── createData           → dati della spedizione (vedi sezione 4)
├── isLabelRequired      → "1" se serve l'etichetta in risposta
├── labelParameters      → opzioni di stampa etichetta
├── actualSender         → mittente reale (solo brtServiceCode=B13)
└── returnShipmentConsignee → destinatario del reso (B13/B14)
```

### 3.2 Struttura `createResponse`

I campi principali della risposta in caso di successo:

| Campo | Note |
|---|---|
| `executionMessage` | `code: 0` = OK. Negativo = errore. Vedi sezione 6. |
| `parcelNumberFrom`, `parcelNumberTo` | range numeri di parcel (= AWB) |
| `arrivalTerminal`, `arrivalDepot` | filiale destinazione |
| `labels` | etichette codificate (se `isLabelRequired=1`) |

---

## 4. Schema `createData` — Lunghezze massime

⚠️ **Tutte le lunghezze sono dichiarate come `maxLength`** nello schema Swagger. Superare il limite genera errore `-68` (WRONG OR INCONSISTENT DATA).

### 4.1 Campi del destinatario (Consignee)

| Campo | Tipo | Max | Note |
|---|---|---|---|
| `consigneeCompanyName` | string | **70** | Ragione sociale / nome+cognome destinatario |
| `consigneeAddress` | string | **35** | ⚠️ **Limite stretto — sorgente di BUG-010** |
| `consigneeZIPCode` | string | 9 | CAP. Deve essere coerente con città/provincia (errore `-63` se incoerente) |
| `consigneeCity` | string | 35 | Città |
| `consigneeProvinceAbbreviation` | string | 2 | Sigla provincia (es. `MI`, `RM`) |
| `consigneeCountryAbbreviationISOAlpha2` | string | 2 | Codice paese ISO Alpha2 (`IT`, `FR`, `GB`...) |
| `consigneeContactName` | string | 35 | Nome contatto (referente) |
| `consigneeTelephone` | string | 16 | Telefono fisso |
| `consigneeMobilePhoneNumber` | string | 16 | Cellulare |
| `consigneeEMail` | string | 70 | Email |
| `consigneeVATNumber` | string | 16 | Partita IVA |
| `consigneeVATNumberCountryISOAlpha2` | string | 2 | Paese P.IVA |
| `consigneeItalianFiscalCode` | string | 16 | Codice fiscale |

### 4.2 Campi spedizione

| Campo | Tipo | Max | Note |
|---|---|---|---|
| `network` | string | 1 | Codice network |
| `departureDepot` | number | — | Filiale di partenza (comunicata da BRT) |
| `senderCustomerCode` | number | — | Codice cliente mittente |
| `deliveryFreightTypeCode` | string | 3 | `DAP` o `EXW` |
| `serviceType` | string | 1 | Tipo servizio |
| `senderParcelType` | string | 15 | Tipo collo |
| `numberOfParcels` | number | — | Quantità colli |
| `weightKG` | number | — | Peso totale |
| `volumeM3` | number | — | Volume |
| `notes` | string | 70 | Note in etichetta |
| `alphanumericSenderReference` | string | 15 | Riferimento ordine alfanumerico |
| `numericSenderReference` | number | — | Riferimento ordine numerico |
| `deliveryDateRequired` | string | 10 | Data richiesta (formato `YYYY-MM-DD`?) |
| `deliveryType` | string | 1 | Tipo consegna |

### 4.3 Contrassegno (Cash on Delivery)

| Campo | Tipo | Max | Note |
|---|---|---|---|
| `cashOnDelivery` | number | — | Importo contrassegno |
| `isCODMandatory` | string | 1 | `S`/`N` |
| `codPaymentType` | string | 2 | Tipo pagamento contrassegno |
| `codCurrency` | string | 3 | Valuta (es. `EUR`) |

### 4.4 Assicurazione

| Campo | Tipo | Max | Note |
|---|---|---|---|
| `insuranceAmount` | number | — | Importo assicurazione |
| `insuranceAmountCurrency` | string | 3 | Valuta |
| `declaredParcelValue` | number | — | Valore dichiarato collo |
| `declaredParcelValueCurrency` | string | 3 | Valuta |

### 4.5 Servizi particolari

| Campo | Tipo | Max | Note |
|---|---|---|---|
| `brtServiceCode` | string | 3 | Codice servizio BRT (`B13` Shop-to-Shop, `B14` Shop-to-Home, `B15` Return-from-Shop, ecc.) |
| `pricingConditionCode` | string | 3 | Condizioni economiche |
| `pudoId` | string | 20 | ID punto PUDO (BRTfermopoint) |
| `parcelsHandlingCode` | string | 2 | Codice gestione colli |
| `particularitiesDeliveryManagementCode` | string | 2 | Gestione particolarità consegna |
| `particularitiesHoldOnStockManagementCode` | string | 2 | Gestione fermo deposito |
| `variousParticularitiesManagementCode` | string | 2 | Altre particolarità |
| `particularDelivery1` | string | 1 | Particolarità consegna 1 |
| `particularDelivery2` | string | 1 | Particolarità consegna 2 |
| `isAlertRequired` | string | 1 | Notifiche di avviso |
| `cmrCode` | string | 35 | Codice CMR (international transport) |

### 4.6 Pallet

| Campo | Tipo | Max | Note |
|---|---|---|---|
| `palletType1` | string | 4 | Tipo pallet 1 |
| `palletType1Number` | number | — | Quantità |
| `palletType2` | string | 4 | Tipo pallet 2 |
| `palletType2Number` | number | — | Quantità |

### 4.7 Mittente originale (drop shipping)

| Campo | Tipo | Max | Note |
|---|---|---|---|
| `originalSenderCompanyName` | string | 25 | Mittente originale (stampato in etichetta) |
| `originalSenderZIPCode` | string | 9 | CAP mittente originale |
| `originalSenderCountryAbbreviationISOAlpha2` | string | 2 | Paese mittente originale |

### 4.8 Autorizzazioni consegna a vicino/codice PIN

| Campo | Tipo | Max | Note |
|---|---|---|---|
| `neighborNameMandatoryAuthorization` | string | 70 | Nome vicino autorizzato |
| `pinCodeMandatoryAuthorization` | string | 35 | Codice PIN obbligatorio |

### 4.9 Packing list PDF

| Campo | Tipo | Max | Note |
|---|---|---|---|
| `packingListPDFName` | string | 33 | Nome file |
| `packingListPDFFlagPrint` | string | 1 | `S`/`N` |
| `packingListPDFFlagEmail` | string | 1 | `S`/`N` |

### 4.10 Resi

| Campo | Tipo | Max | Note |
|---|---|---|---|
| `returnDepot` | number | — | Filiale di reso |

---

## 5. Schema `createData` — Campi obbligatori

Estratti dalle annotazioni "Mandatory data" nella documentazione HTML:

- `departureDepot`
- `senderCustomerCode`
- `deliveryFreightTypeCode`
- `consigneeCompanyName`
- `consigneeAddress`
- `consigneeZIPCode`
- `consigneeCity`
- `consigneeCountryAbbreviationISOAlpha2`
- `numberOfParcels`
- `weightKG`
- `isCODMandatory`
- `numericSenderReference`
- `deliveryDateRequired`
- `deliveryType`
- `brtServiceCode`
- `returnDepot`

⚠️ **Nota su `palletType1Number` / `palletType2Number`**: marcati come Mandatory in alcune righe ma probabilmente solo quando il corrispondente `palletType1/2` è valorizzato. Da verificare nella documentazione di dettaglio.

⚠️ **Nota su `cmrCode` / `neighborNameMandatoryAuthorization` / `pinCodeMandatoryAuthorization`**: marcati Mandatory ma in contesti specifici (trasporti internazionali, autorizzazioni delivery). Non sempre richiesti.

---

## 6. Catalogo codici errore

Da `executionMessage.code` nella risposta. **Valore `0` = OK**, valori negativi = errore.

### Errori (HTTP 200 con `executionMessage.code` negativo)

| Codice | Nome breve | Descrizione |
|---|---|---|
| `-7` | LOGIN_FAILED | Login fallito (credenziali invalide) |
| `-57` | LOGIN_PARAMETER_MISSING | Parametro login mancante |
| `-63` | ROUTING_CALCULATION_ERROR | Errore calcolo routing (es. CAP/città non coerenti) |
| `-64` | PARCEL_NUMBERING_ERROR | Errore numerazione collo |
| `-65` | LABEL_PRINTING_ERROR | Errore stampa etichetta |
| `-67` | USER_ACCOUNT_ERROR | `senderCustomerCode` non collegato all'`userID` di autenticazione |
| `-68` | WRONG_OR_INCONSISTENT_DATA | Dato errato o incoerente. Vedi `message` dettagliato per il campo specifico. Esempi: lunghezza eccessiva, paese GB senza email/cellulare (post-Brexit), return depot inesistente |
| `-69` | PUDO_NOT_VALID | `pudoId` non valido o inesistente |
| `-101` | SHIPMENT_NOT_CONFIRMABLE | Spedizione non può essere confermata |
| `-102` | SHIPMENT_ALREADY_CONFIRMED | Spedizione già confermata |
| `-151` | SHIPMENT_TOO_OLD_OR_MISSING | Mai creata oppure creata > 40 giorni fa |
| `-152` | SHIPMENT_BEING_HANDLED | Spedizione già in lavorazione al deposito |
| `-153` | SHIPMENT_BEING_PROCESSED | In elaborazione, riprovare |
| `-154` | MULTIPLE_SHIPMENTS_FOUND | Più spedizioni con stessi identificativi |
| `-155` | ALLOCATED_FOR_DELETION | Record allocato per cancellazione |

### Warning (operazione riuscita con avviso)

| Codice | Descrizione |
|---|---|
| `4` | Dati normalizzati (Città/CAP/Provincia) — BRT ha corretto autonomamente |
| `5` | Indirizzo destinatario sostituito con quello del PUDO BRTfermopoint |
| `6` | Dati destinatario impostati con dati del return depot |

---

## 7. Regole di pre-validazione raccomandate

⚠️ **Strategia consigliata**: validare lato BE/FE i casi più frequenti e ovvi (lunghezza, presenza campi obbligatori), lasciar gestire al wrapper errori (FE-7) i casi residui (regole proprietarie BRT non sempre prevedibili).

### 7.1 Validazioni di lunghezza (per BRT)

**Campi a rischio "troppo lungo"** nel dominio italiano tipico:

| Campo BRT | Limite | Sorgente dati Elettronew | Frequenza errore |
|---|---|---|---|
| `consigneeAddress` | 35 | `address.address1` | **Alta** — gli indirizzi italiani superano spesso 35 |
| `consigneeCity` | 35 | `address.city` | Bassa |
| `consigneeCompanyName` | 70 | `address.company` o `firstname + lastname` | Bassa |
| `consigneeContactName` | 35 | `address.firstname + lastname` | Media |
| `consigneeEMail` | 70 | `customer.email` | Bassa |
| `consigneeTelephone` | 16 | `address.phone` | Bassa |
| `consigneeMobilePhoneNumber` | 16 | `address.mobile_phone` | Bassa |
| `notes` | 70 | `note` dell'ordine | Media |
| `alphanumericSenderReference` | 15 | numero documento? | Media |

### 7.2 Validazioni di coerenza (per BRT)

- **CAP coerente con città/provincia** — il -63 di BUG-010 suggerisce che BRT verifica la coerenza. Valutare validazione con tabella CAP italiani (libreria, dataset Poste).
- **`brtServiceCode` valido** — quando l'utente usa servizi specifici (B13, B14, B15), assicurarsi che i campi aggiuntivi (`actualSender`, `returnShipmentConsignee`) siano presenti.
- **`isCODMandatory` coerente con `cashOnDelivery`** — se uno è valorizzato, l'altro deve esserlo.
- **`palletTypeNNumber` coerente con `palletTypeN`** — pallet dichiarati ma quantità mancante = invalido.

### 7.3 Cosa NON validare lato nostro

Lasciamo che BRT risponda con errore (e gestiamo bene la presentazione via `extractErrorMessage`):
- Esistenza `senderCustomerCode` / `departureDepot` (sono comunicati da BRT)
- Validità formato CAP estero
- Compatibilità servizio con destinazione (es. PUDO solo in IT)
- Regole post-Brexit per GB

---

## 8. Mapping con il dominio Elettronew

Mappatura tentativa tra modelli Elettronew e campi BRT (da verificare in `carrier_api/brt_service.py` lato BE):

| Campo BRT | Modello Elettronew | Note |
|---|---|---|
| `consigneeCompanyName` | `Address.company` (fallback: `firstname + " " + lastname`) | Truncare a 70 |
| `consigneeAddress` | `Address.address1` (eventualmente `+ " " + address2`) | **⚠️ Truncare a 35 o validare** |
| `consigneeZIPCode` | `Address.postcode` | Verificare formato per IT |
| `consigneeCity` | `Address.city` | Truncare a 35 |
| `consigneeProvinceAbbreviation` | `Address.state` (se 2 caratteri) | Stato/provincia |
| `consigneeCountryAbbreviationISOAlpha2` | `Country.iso_code` | 2 chars (IT, FR, ...) |
| `consigneeContactName` | `Address.firstname + " " + Address.lastname` | Truncare a 35 |
| `consigneeTelephone` | `Address.phone` | Truncare a 16 |
| `consigneeMobilePhoneNumber` | `Address.mobile_phone` | Truncare a 16 |
| `consigneeEMail` | `Customer.email` | Truncare a 70 |
| `consigneeVATNumber` | `Address.vat` | Truncare a 16 |
| `consigneeItalianFiscalCode` | `Address.dni` (codice fiscale) | Truncare a 16 |
| `weightKG` | `Order.total_weight` o `Shipping.weight` | |
| `numberOfParcels` | `count(OrderPackage)` o `Shipping.number_of_parcels` | |
| `cashOnDelivery` | `Order.cash_on_delivery` | |
| `numericSenderReference` | `Order.id_order` | |
| `alphanumericSenderReference` | `Order.reference` | Truncare a 15 |
| `notes` | `Order.note` o `Shipping.shipping_message` | Truncare a 70 |
| `senderCustomerCode` | configurazione `app_configurations.brt_customer_code` (?) | Comunicato da BRT |
| `departureDepot` | configurazione `app_configurations.brt_departure_depot` (?) | Comunicato da BRT |
| `account.userID` / `password` | configurazione carrier API credentials | |

⚠️ Da verificare quando si guarderà il codice reale in `carrier_api/brt_service.py`.

---

## 📚 Fonti

- `RestShipmentProd.en/SwaggerViewerShipment.json` — definizioni complete schemi
- `RestShipmentProd.en/ShipmentApiV00_ws.html` — descrizione testuale endpoint + codici errore
- `RestShipmentProd.en/ShipmentApiV00_ws~j-createData.html` — dettagli campi createData con "Mandatory"
- `RestShipmentProd.en/ShipmentApiV00_ws~r--shipment~o-HttpPost.html` — esempio POST /shipment
