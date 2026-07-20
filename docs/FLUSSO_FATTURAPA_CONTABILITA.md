# FatturaPA — Flusso operativo (riassunto per Contabilità)

**Sistema:** Elettronew · **Formato:** FatturaPA FPR12 · **Intermediario:** FatturaPA.com  
**Versione documento:** 2026-07-20

---

## A cosa serve

Il gestionale crea la **fattura elettronica** a partire da un ordine e-commerce, genera l’**XML FatturaPA**, lo carica sull’**intermediario** e (se autorizzato) lo invia allo **SDI**. Produce anche un **PDF di cortesia** per archivio/cliente.

La fattura è uno **snapshot**: dopo l’emissione, le modifiche all’ordine non aggiornano il documento già emesso.

---

## Flusso in 5 passi

```
ORDINE PRONTO
     │
     ▼
① CREA FATTURA DA ORDINE          → status: pending
     │
     ▼
② GENERA XML FATTURAPA            → status: generated
     │                              (validazione automatica dati)
     ▼
③ CARICA SU FATTURAPPA.COM        → status: uploaded  (default: SENZA invio SDI)
     │
     ▼
④ [OPZIONALE] INVIO SDI           → status: sent      (solo se autorizzato)
     │
     ▼
⑤ PDF DI CORTESIA                 (archivio / cliente)
```

---

## Passo 1 — Creazione fattura da ordine

| | |
|---|---|
| **Cosa fa** | Crea il documento fiscale con numero progressivo annuale (es. 000016) |
| **Cosa salva** | Righe ordine, prezzi, IVA, spedizione (snapshot) |
| **Status risultante** | `pending` |
| **Chi** | Operatore gestionale (permesso creazione fatture) |

**Prima di procedere, verificare sull’ordine:**

- Indirizzo di **fatturazione** completo
- **Cliente IT:** P.IVA oppure Codice Fiscale + ragione sociale o nome/cognome
- **Cliente UE B2B (VIES):** P.IVA estera valida + esenzione VIES già applicata (vedi sotto)

---

## Passo 2 — Generazione XML

| | |
|---|---|
| **Cosa fa** | Produce il file XML FatturaPA e lo archivia nel sistema |
| **Status risultante** | `generated` |
| **Se fallisce** | Errore con elenco campi da correggere (es. P.IVA errata, CAP mancante) |

**Controlli automatici principali:**

| Controllo | Cliente IT | Cliente UE (VIES) |
|-----------|------------|-------------------|
| P.IVA / CF | P.IVA o CF obbligatorio | P.IVA estera obbligatoria |
| Indirizzo | Via, CAP (5 cifre), comune, provincia (2 lettere) | Via, CAP, comune; provincia opzionale |
| Codice destinatario SDI | SDI cliente (7 char) o `0000000` B2C | `XXXXXXX` (automatico) |
| IVA righe | Aliquota da ordine | Prodotti: 0% + natura **N3.2** se VIES |

---

## Passo 3 — Upload su FatturaPA.com

| | |
|---|---|
| **Cosa fa** | Carica l’XML sull’intermediario FatturaPA.com |
| **Default** | Solo upload, **senza** invio allo SDI |
| **Status risultante** | `uploaded` |
| **Prerequisito** | XML già generato (passo 2) |

---

## Passo 4 — Invio SDI (solo se autorizzato)

| | |
|---|---|
| **Cosa fa** | Trasmette la fattura al Sistema di Interscambio (SDI) |
| **Status risultante** | `sent` |
| **Quando** | Solo in **produzione**, dopo approvazione contabilità / direzione |

> **In fase test/collaudo** si usa normalmente solo l’upload (passo 3), senza invio SDI.

---

## Passo 5 — PDF di cortesia

PDF della singola fattura per archivio interno o invio al cliente.  
**Non sostituisce** l’XML FatturaPA ai fini fiscali.

---

## Caso speciale: operazioni intra-UE (VIES)

Per fatture B2B verso clienti UE con reverse charge:

```
1. Verificare P.IVA estera del cliente
2. Applicare esenzione VIES sull’ordine
      → IVA prodotti a 0%, natura N3.2 nell’XML
3. Creare fattura elettronica (passo 1)
4. Generare XML (passo 2)
5. Upload / SDI (passi 3–4)
```

**Importante:** l’esenzione VIES va applicata **prima** di creare la fattura.

---

## Stati del documento

| Status | Significato |
|--------|-------------|
| `pending` | Fattura creata, XML da generare |
| `generated` | XML prodotto e archiviato |
| `uploaded` | Caricata su FatturaPA.com, non inviata SDI |
| `sent` | Inviata allo SDI |
| `error` | Errore upload o invio |
| `issued` | Fattura non elettronica (senza XML) |

---

## Export massivo XML (uso amministrativo)

Per estrarre più fatture in un unico ZIP:

- **Filtri:** solo range date + paese **consegna**
- **Nessun filtro** per status
- Se manca l’XML, il sistema tenta di generarlo in automatico
- Il PDF resta sempre singolo (una fattura alla volta)

---

## Test vs produzione

| | Collaudo | Produzione |
|---|----------|------------|
| Account FatturaPA.com | Demo / sandbox | Produzione |
| Invio SDI | Di norma **disattivato** | Attivato dopo go-live |
| Dati ordini | Possono essere di test | Devono essere reali e corretti |

---

## Cosa il sistema non fa ancora (da sapere)

- Notifiche automatiche SDI (ricevuta, scarto) — in sviluppo
- Validazione XSD ufficiale AgEntrate — parziale
- Gestione completa errori SDI e retry — in backlog

---

## Responsabilità suggerite

| Attività | Responsabile |
|----------|--------------|
| Verifica dati cliente (P.IVA, SDI, indirizzo) | Contabilità / Customer care |
| Applicazione VIES su ordini UE | Contabilità |
| Creazione fattura e generazione XML | Operatore gestionale |
| Autorizzazione invio SDI in produzione | Contabilità / Direzione |
| Configurazione intermediario e API key | IT + Contabilità |

---

## Checklist approvazione go-live

- [ ] Dati cedente verificati (P.IVA, indirizzo, regime fiscale RF01)
- [ ] Account FatturaPA.com produzione attivo
- [ ] Procedura VIES intra-UE definita e testata
- [ ] Test generazione XML su campione fatture IT e UE OK
- [ ] Test upload intermediario OK
- [ ] Procedura invio SDI approvata
- [ ] Procedura gestione scarti/errori definita

---

## Riferimenti tecnici (per IT)

- Guida completa: [`docs/FATTURAPA.md`](./FATTURAPA.md)
- API: `/api/v1/fiscal_documents` · Swagger: `/docs` → tag **Fiscal Documents**

---

*Documento generato dal team di sviluppo Elettronew API — per domande operative contattare IT o referente contabilità.*
