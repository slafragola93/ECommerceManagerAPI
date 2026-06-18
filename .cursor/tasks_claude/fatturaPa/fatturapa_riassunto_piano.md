# FatturaPA – Riassunto Tecnico e Piano di Implementazione
**Progetto:** Elettronew | **Aggiornato:** Giugno 2026

---

## 1. Punti Chiave della Documentazione Ufficiale

### 1.1 Formato del File

- **XML obbligatorio** secondo lo schema FatturaPA. La versione corrente è la **1.9.1**, in vigore dal 15 maggio 2026 (sostituisce la 1.9 del 1° aprile 2025). I file non conformi vengono **scartati automaticamente** dallo SDI.
- La struttura XML è divisa in:
  - `FatturaElettronicaHeader` — dati cedente/prestatore e cessionario/committente
  - `FatturaElettronicaBody` — dati generali, righe beni/servizi, importi IVA, riepilogo, dati pagamento
- Il file può essere inviato singolo o compresso in **ZIP** (più file XML). Dimensione massima: **5 MB** (canale Web Service/PEC); fino a **150 MB** via SFTP/FTP.
- La firma digitale è **obbligatoria per le fatture B2G** (verso la PA); facoltativa per B2B/B2C.

### 1.2 Campi Fondamentali

| Campo | Descrizione |
|---|---|
| `TipoDocumento` | Codici TD01–TD29 (es. TD01=fattura, TD04=nota di credito, TD29=nuovo 2025) |
| `RegimeFiscale` | Codici RF01–RF20 (es. RF01=ordinario, RF19=forfettario, RF20=franchigia transfrontaliera) |
| `CodiceDestinatario` | Codice univoco 7 cifre del canale SDI del destinatario |
| `NaturaIVA` | Codici N1–N7 per operazioni esenti/escluse (N7 = regime OSS) |
| `AliquotaIVA` | Aliquota percentuale (0, 4, 10, 22, ecc.) |
| `CUU` | Codice Univoco Ufficio (per fatture verso PA) |
| `CUP/CIG` | Codice progetto/gara, obbligatorio in molti appalti pubblici |

### 1.3 Novità Specifiche v1.9.1 (dal 15 maggio 2026)

- **Gruppi IVA**: controllo obbligatorio del codice fiscale del singolo partecipante al gruppo (non del gruppo IVA nel complesso). Errore `00327` in caso di mismatch.
- **Lavoratori sportivi dilettantistici**: nuova codifica nel blocco `AltriDatiGestionali`.
- **Numero massimo di codici destinatario** per P.IVA: ora limitato.
- **Procedure di accreditamento aggiornate** per i canali WS e SFTP.

### 1.4 Canali di Trasmissione verso lo SDI

| Canale | Protocollo | Limite dimensione | Note |
|---|---|---|---|
| **PEC** | Email certificata | 30 MB | Indirizzo: `sdi01@pec.fatturapa.it` |
| **SdICoop (Web Service)** | HTTPS/SOAP | 5 MB | Richiede accreditamento e certificato |
| **SdIFTP / SFTP** | FTP/SFTP cifrato | 150 MB | Per grandi volumi; richiede accreditamento |
| **Portale Fatture e Corrispettivi** | Web UI | 5 MB | Manuale, non integrabile da gestionale |

> Per un gestionale come **Elettronew**, il canale realistico è uno tra:
> - **Intermediario con API REST** (Aruba, Openapi, ecc.) — percorso più rapido
> - **SdICoop accreditato direttamente** — percorso autonomo, più complesso

### 1.5 Ciclo di Vita della Fattura

```
Gestionale → Genera XML → [Firma opzionale] → Invia a SDI
    ↓
SDI valida formalmente il file
    ├─ SCARTO → Notifica di scarto (correggere e reinviare entro 5 gg)
    └─ OK → Consegna al destinatario
              ├─ B2G: destinatario può RIFIUTARE (invia notifica esito)
              └─ B2B: consegnata, non rifiutabile (solo nota di credito)
```

- Lo SDI risponde con notifiche XML: `RC` (ricevuta di consegna), `NS` (notifica di scarto), `NE` (notifica esito), `MC` (mancata consegna), `AT` (attestazione di trasmissione).
- **Conservazione digitale a norma obbligatoria per 10 anni** (l'AdE conserva automaticamente, ma è consigliato un backup locale).
- Obbligo di invio entro **12 giorni** dalla data dell'operazione.

---

## 2. Strategia di Integrazione Consigliata per Elettronew

Dato che Elettronew è un gestionale custom FastAPI/MySQL, la strada consigliata è usare un **intermediario certificato con API REST** (es. Aruba FE, Openapi.com, Fattura24, ecc.), evitando l'accreditamento diretto allo SDI (che richiede certificati qualificati, test di interoperabilità e gestione SOAP/SFTP).

Il gestionale:
1. **genera l'XML** conforme alle specifiche
2. **chiama le API REST** dell'intermediario
3. **riceve lo stato** via webhook o polling

---

## 3. Piano di Lavoro – Backlog FatturaPA

### FASE 0 — Prerequisiti e Decisioni Architetturali (1–2 gg)

| ID | Task | Note |
|---|---|---|
| FE-PA-0.1 | Scegliere l'intermediario SDI | Confrontare Aruba FE, Openapi, Fattura24, ecc. su costo/API |
| FE-PA-0.2 | Aprire account sandbox/demo intermediario | Necessario per i test |
| FE-PA-0.3 | Definire la tabella `fatture_elettroniche` nel DB | Campi: id, ordine_id, xml_content, stato_sdi, notifiche_json, timestamps |
| FE-PA-0.4 | Verificare dati anagrafici azienda nel DB | P.IVA, regime fiscale, indirizzo, CAP — tutto conforme allo schema XSD |

### FASE 1 — Generazione XML FatturaPA (3–5 gg)

| ID | Task | Stack |
|---|---|---|
| BE-PA-1.1 | Implementare il builder XML (`fatturapa_builder.py`) | Python `lxml` o `xml.etree` |
| BE-PA-1.2 | Mappare i campi Elettronew → campi FatturaPA | Header, DatiGenerali, DettaglioLinee, DatiRiepilogo |
| BE-PA-1.3 | Gestire TipoDocumento: TD01 (fattura), TD04 (nota di credito) | Aggiungere altri TD in futuro |
| BE-PA-1.4 | Gestire NaturaIVA / AliquotaIVA (riusare logica VIES già esistente) | Attenzione alle esenzioni VIES → N3.4 |
| BE-PA-1.5 | Validazione XSD del file generato prima dell'invio | Scaricare XSD ufficiale v1.2.3 da fatturapa.gov.it |
| BE-PA-1.6 | Unit test generazione XML con dati reali | Coprire casi: IVA ordinaria, esente, VIES |

### FASE 2 — Integrazione API Intermediario — Ciclo Attivo (3–4 gg)

| ID | Task | Stack |
|---|---|---|
| BE-PA-2.1 | Implementare `FatturapaService` con metodo `send_invoice(xml: str)` | `httpx` async |
| BE-PA-2.2 | Gestire risposta asincrona: salvataggio `protocollo_sdi` e stato iniziale | DB update |
| BE-PA-2.3 | Endpoint webhook per ricezione notifiche SDI (NS/RC/NE/MC) | `POST /api/fatturapa/webhook` |
| BE-PA-2.4 | Aggiornare stato fattura nel DB a ogni notifica ricevuta | Stato: `bozza → inviata → consegnata → scartata` |
| BE-PA-2.5 | Endpoint `GET /api/fatture/{id}/stato` per consultazione stato | Usato dal FE |

### FASE 3 — Frontend — Visualizzazione e Azioni (2–3 gg)

| ID | Task | Stack |
|---|---|---|
| FE-PA-3.1 | Aggiungere colonna "Stato SDI" nella lista fatture | Angular, NgRx |
| FE-PA-3.2 | Azione "Invia a SDI" da dettaglio ordine/fattura | Dispatch action → effect → BE |
| FE-PA-3.3 | Badge stato (bozza / inviata / consegnata / scartata / rifiutata) | Pipe + colori |
| FE-PA-3.4 | Visualizzare le notifiche SDI ricevute (timeline) | Componente storico notifiche |
| FE-PA-3.5 | Download XML e PDF della fattura emessa | Link download da BE |

### FASE 4 — Ciclo Passivo e Conservazione (2–3 gg, opzionale)

| ID | Task | Note |
|---|---|---|
| BE-PA-4.1 | Polling/webhook per ricezione fatture passive (da fornitore) | Solo se si vuole integrazione completa |
| BE-PA-4.2 | Salvataggio XML fatture ricevute nel DB | Tabella `fatture_passive` |
| BE-PA-4.3 | Interfaccia di consultazione fatture ricevute | FE — lista con filtri |
| BE-PA-4.4 | Verifica conservazione a norma | L'intermediario spesso la gestisce; confermare contrattualmente |

### FASE 5 — Test e Go-Live (2–3 gg)

| ID | Task |
|---|---|
| BE-PA-5.1 | Test end-to-end in ambiente sandbox intermediario |
| BE-PA-5.2 | Generare fattura di test con P.IVA reale in ambiente SDI di collaudo AdE |
| BE-PA-5.3 | Verificare ricezione notifiche di consegna e gestione scarti |
| BE-PA-5.4 | Stress test con invio multiplo (batch) |
| BE-PA-5.5 | Switch a produzione + monitoraggio prime fatture reali |

---

## 4. Rischi e Note Tecniche

| Rischio | Mitigazione |
|---|---|
| File XML scartato da SDI | Validare sempre con XSD ufficiale prima dell'invio (fase BE-PA-1.5) |
| Notifiche SDI perse | Implementare anche polling periodico oltre al webhook |
| Dati anagrafici errati (P.IVA non valida) | Riusare la logica VIES già presente in Elettronew |
| Aggiornamenti specifiche tecniche | Iscriversi alla newsletter AdE; monitorare fatturapa.gov.it |
| Cambio intermediario in futuro | Isolare l'integrazione in un service dedicato (`FatturapaService`) |

---

## 5. Riferimenti Ufficiali

- Schemi XSD v1.2.3: https://www.fatturapa.gov.it/it/norme-e-regole/documentazione-fattura-elettronica/formato-fatturapa/
- Specifiche SDI v1.9.1 (dal 15/05/2026): https://www.fatturapa.gov.it/it/norme-e-regole/DocumentazioneSDI/
- Elenco controlli v2.0: https://www.fatturapa.gov.it/it/ricerca/index.html
- Portale Fatture e Corrispettivi (test/validazione): https://ivaservizi.agenziaentrate.gov.it/
- Normativa AgE: https://www.agenziaentrate.gov.it/portale/normativa-prassi-e-regole-tecniche-fatture-elettroniche
