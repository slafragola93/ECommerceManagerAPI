# TASKS BE — Ricevute per l'estero

## Contesto

Documento sostitutivo emesso per clienti privati esteri senza P.IVA che richiedono un
documento fiscale. Non viene inviato a FatturaPA/SDI: è un documento esclusivamente
interno. Nasce come soluzione alternativa alla fattura con natura code particolare,
non supportata dal gestionale legacy.

Riferimento incrociato: `TASKS_FE_ricevute.md` (repo FE) · handoff BE step 1: `docs/FE_HANDOFF_RICEVUTE.md` · prompt chat FE: `.cursor/tasks_claude/fatturazione/prompt_FE_ricevute.md`

---

## FASE 1 — Schema database

### BE-1.1 — Tabella `ricevute`

```sql
CREATE TABLE ricevute (
    id                      INT PRIMARY KEY AUTO_INCREMENT,
    numero                  INT NOT NULL,
    anno                    SMALLINT NOT NULL,

    order_id                INT NOT NULL,
    customer_id             INT NOT NULL,

    data_incasso            DATE NOT NULL,
    data_emissione          DATE NOT NULL,

    stato                   ENUM('emessa','annullata') DEFAULT 'emessa',

    pdf_path                VARCHAR(500),
    pdf_hash                VARCHAR(128),
    pdf_generated_at        TIMESTAMP NULL,

    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    annullata_at            TIMESTAMP NULL,
    annullata_da_user_id    INT NULL,

    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    UNIQUE (numero, anno)
);

CREATE INDEX idx_ricevute_incasso ON ricevute(data_incasso, stato);
CREATE INDEX idx_ricevute_emissione ON ricevute(data_emissione, stato);
CREATE INDEX idx_ricevute_order ON ricevute(order_id);
```

**Note di design (non ridiscutere, già validate):**
- Nessuna tabella righe: prodotti/quantità/prezzi si recuperano via `order_id` → `orders`/`order_details`, sempre live.
- Nessuna tabella cliente-snapshot: dati anagrafici via `customer_id` → `customers`, sempre live.
- Nessun `natura_code`: la ricevuta non va a SDI, il campo non ha senso qui.
- Nessun campo `locked`: la modificabilità deriva dallo stato dell'ordine collegato, non da un flag persistito.
- Nessuno storico versioni PDF: `pdf_path`/`pdf_hash`/`pdf_generated_at` vengono sovrascritti ad ogni rigenerazione.
- Nessuna tabella di movimenti/rettifiche sui corrispettivi: i corrispettivi non sono mai persistiti, quindi non possono avere FK verso record che non esistono.

### BE-1.2 — Migrazione + seed numerazione

- Migration per la tabella sopra.
- Verificare che la numerazione (`numero`, `anno`) riparta da 1 ad ogni nuovo anno solare.
- Gestire la concorrenza sulla generazione del numero progressivo (lock ottimistico o `SELECT ... FOR UPDATE` sul max numero dell'anno corrente).

---

## FASE 2 — Endpoint CRUD ricevuta

### BE-2.1 — `POST /api/v1/ricevute`

Input: `order_id`, `data_emissione` (default: data corrente).

Logica:
1. Validare che l'ordine esista e sia in uno stato compatibile (non ancora "Spedizione confermata" — vedi BE-2.4).
2. Recuperare `customer_id` dall'ordine.
3. `data_incasso` = data di pagamento dell'ordine (troncata a `DATE`, stessa logica di troncamento usata per il corrispettivo — vedi BE-3.1, per evitare disallineamenti di fuso orario).
4. Calcolare `numero`/`anno` progressivo.
5. Creare il record con `stato = 'emessa'`.
6. Triggerare la generazione PDF (BE-2.3).

**Blocking dependency:** BE-3.1 deve definire la stessa logica di troncamento data usata qui, per coerenza tra `orders.data_pagamento` e `ricevute.data_incasso`.

### BE-2.2 — `GET /api/v1/ricevute/{id}` e `GET /api/v1/ricevute` (lista/filtri)

- Filtri minimi: per `order_id`, `customer_id`, `stato`, range `data_emissione`.
- La risposta include i dati cliente/ordine/righe recuperati via join live (non serve un DTO che li duplichi in cache).

### BE-2.3 — Generazione/rigenerazione PDF

- `POST /api/v1/ricevute/{id}/pdf` (o generazione automatica alla creazione, da confermare con FE).
- Il PDF si genera sempre a partire dai dati **correnti** di ordine/cliente (join live).
- Ogni rigenerazione **sovrascrive** `pdf_path`/`pdf_hash`/aggiorna `pdf_generated_at`. Nessuno storico.
- Campi da includere nel PDF: stessi di una fattura, meno lo SDI (dati cliente, dati venditore, righe prodotto con quantità/prezzo/aliquota, totali netto/IVA/lordo, numero/anno, data emissione, causale/note).

### BE-2.4 — Modifica / eliminazione (soft delete)

- `PUT /api/v1/ricevute/{id}` e `DELETE /api/v1/ricevute/{id}` (soft delete → `stato = 'annullata'`, `annullata_at`, `annullata_da_user_id`).
- **Unico controllo applicativo**: bloccare l'operazione se `orders.stato == 'Spedizione confermata'`.
- **Nessun controllo automatico sullo stato del corrispettivo**: resta una verifica manuale dell'utente, non implementare nulla lato BE su questo.
- Mai cancellazione fisica del record.

### BE-2.5 — Export CSV/Excel

- `GET /api/v1/ricevute/{id}/export?fmt=csv|xlsx` per singola ricevuta.
- Valutare endpoint aggiuntivo per export massivo (range di date), utile per uso contabile/commercialista — da confermare priorità con Francesca.

### BE-2.6 — Invio email

- `POST /api/v1/ricevute/{id}/invia-mail`.
- Nessun vincolo di canale essendo documento non-SDI: email libera con PDF allegato.

---

## FASE 3 — Corrispettivo live (impatto dell'introduzione ricevute)

### BE-3.1 — Query corrispettivo singola data

Aggiornare il servizio esistente di calcolo corrispettivo per includere la
decurtazione/imputazione delle ricevute:

```sql
SELECT
    (SELECT COALESCE(SUM(o.totale_lordo), 0) FROM orders o
     WHERE DATE(o.data_pagamento) = :data AND o.stato = 'completato')
  - (SELECT COALESCE(SUM(o.totale_lordo), 0)
     FROM ricevute r JOIN orders o ON o.id = r.order_id
     WHERE r.data_incasso = :data AND r.stato = 'emessa')
  + (SELECT COALESCE(SUM(o.totale_lordo), 0)
     FROM ricevute r JOIN orders o ON o.id = r.order_id
     WHERE r.data_emissione = :data AND r.stato = 'emessa')
AS corrispettivo_lordo;
```

Importo recuperato sempre da `orders.totale_lordo` via join — nessun ricalcolo dalle righe.

**Attenzione:** allineare il troncamento data tra `orders.data_pagamento` (presumibilmente DATETIME) e `ricevute.data_incasso`/`data_emissione` (DATE), per evitare che un ordine pagato in tarda serata risulti disallineato di un giorno tra le due tabelle.

### BE-3.2 — Query corrispettivo per range (dashboard/report periodico)

Non iterare la query per singolo giorno in loop applicativo. Usare `UNION ALL` + `GROUP BY data` tra base ordini e le due direzioni delle ricevute, così da ottenere in un'unica query sia il totale finale sia la scomposizione (base / decurtato / imputato) per giorno, utile per audit visivo.

Deve poter essere richiamata per qualsiasi range storico (anche mesi passati), essendo il corrispettivo sempre generato live e mai persistito.

### BE-3.3 — Verifica compatibilità con la logica Resi esistente

Confermare che la logica di ripristino automatico dei resi eliminati (già esistente, comportamento confermato: l'importo si ripristina nel corrispettivo alla data ordine originale) non collida con la nuova decurtazione/imputazione delle ricevute quando entrambe insistono sullo stesso ordine nello stesso periodo. Da verificare con un test di integrazione dedicato.

---

## FASE 4 — Endpoint di supporto per il FE

### BE-4.1 — Stato ordine per abilitazione azioni

Esporre (o riusare se già presente) un modo per il FE di sapere se un ordine è ancora
"modificabile" ai fini ricevuta (`stato != 'Spedizione confermata'`), per abilitare/disabilitare
lato client i pulsanti Modifica/Elimina senza dover tentare la chiamata e ricevere un errore.

### BE-4.2 — Azione "Genera ricevuta" da modale ordine

Endpoint dedicato o riuso di BE-2.1 richiamato dal modale dettaglio ordine (vedi
`TASKS_FE_ricevute.md`, task collegato). Verificare che risponda con i dati sufficienti
al FE per aprire direttamente l'anteprima/PDF senza chiamata aggiuntiva.

---

## Note aperte / da validare con Francesca

- Priorità dell'export massivo (range) per uso contabile.
- Formato esatto del PDF (layout, dati venditore, dicitura sostitutiva della fattura).
