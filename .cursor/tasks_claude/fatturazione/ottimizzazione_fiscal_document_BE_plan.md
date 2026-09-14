# Ottimizzazione oggetto FiscalDocument — Step BE

Obiettivo: ridurre payload e ridondanza dei campi negli endpoint fiscal-documents (fatture e note di credito), senza rompere i consumer FE prima che siano aggiornati. Procedere step per step, con test-gate ad ogni step.

## Step 1 — Fix duplicazione response wrapper (nessuna modifica di schema)
- Nell'endpoint di lista, restituire una sola chiave tra `items` e `invoices` (verificare prima con il FE quale sia effettivamente usata).
- Test-gate: nessuna rottura sui test esistenti degli endpoint di lista.
- **Fatto (2026-09-14):** `GET /orders/{id}/invoices` tiene solo `invoices` (scelta: più intuitivo di `items`). Resi/ricevute invariati.

## Step 2 — Spostare `xml_content` su endpoint dedicato
- Rimuovere `xml_content` dal payload di default di lista e dettaglio.
- Aggiungere `GET /fiscal-documents/{id}/xml` (o endpoint di download) che lo restituisce on-demand.
- Se serve un periodo di transizione, mantenere temporaneamente un query param (`?include_xml=true`), da rimuovere a fine migrazione FE.
- Test-gate: confronto dimensione payload di lista prima/dopo; test sul nuovo endpoint.
- **Fatto (2026-09-14):** `GET /api/v1/fiscal_documents/{id}/xml`; lista/dettaglio omettono `xml_content`; `?include_xml=true` solo sul dettaglio.

## Step 3 — Rendere `filename` un campo calcolato, non spedito come dato fisso
- Verificare se oggi è colonna DB o già calcolato in serializzazione.
- Se è colonna DB: non toccare lo storico, aggiungere property calcolata (VAT cedente + `progressivo_invio`) nello schema di risposta; la colonna può restare, deprecata.
- Test-gate: il filename calcolato coincide con quello storico su un campione di documenti reali.
- **Fatto (2026-09-14):** `compute_fatturapa_response_filename` in lista/dettaglio; colonna DB invariata come fallback.

## Step 4 — Ripulire `upload_result`
- Eliminare il campo dalla risposta, o assorbire l'eventuale `message` extra dentro `fatturapa_error_message`.
- Verificare che nessun job/servizio interno dipenda dal parsing di quella stringa.

## Step 5 — Chiarire `status` vs `fatturapa_status`
- Verificare nel codice se `status` è sempre copiato da `fatturapa_status` o rappresenta un concetto diverso.
- Se sempre sincronizzati: eliminare uno dei due (valutare impatto su filtri/query che li usano).
- ⚠️ Se comporta drop di colonna via Alembic: conferma esplicita richiesta prima di procedere.

## Step 6 — Raggruppare gli stati per sottosistema (`lifecycle`)
- Da coordinare con lo Step 3 del piano P0 già approvato (tabella storico SDI notifications + `sdi_status` separato).
- Nuova struttura response:
  ```json
  "lifecycle": {
    "status": "sent",
    "fatturapa": {"status": "sent", "error_message": null, "identificativo_sdi": null},
    "sdi": {"status": null, "error_message": null},
    "mail": {"status": null, "error_message": null}
  }
  ```
- Mantenere i campi flat esistenti in parallelo finché il FE non è aggiornato (deprecare, non rimuovere subito).
- ⚠️ Eventuale migrazione Alembic: conferma esplicita richiesta prima di procedere.

## Step 7 — Rendere condizionali i campi solo-NC
- `credit_note_reason` e `is_partial` esclusi dalla risposta quando `document_type == "invoice"`.
- Valutare due modelli Pydantic distinti (`InvoiceOut` / `CreditNoteOut`, discriminated union) invece di un modello unico con tutto opzionale.

## Step 8 — Aggiungere indicatore di storno sulla fattura
- Nuovo campo calcolato (non persistito, stesso pattern dei corrispettivi) `stato_storno` su `InvoiceOut`: `non_stornata` / `parziale` / `totale`, calcolato sommando le NC collegate via `id_fiscal_document_ref`.
- Aggiungere validazione lato creazione NC: bloccare la creazione se il residuo stornabile è già zero.
- Test-gate: casi per storno parziale, totale, tentativo di storno oltre il residuo.

## Step 9 — Valutare ridondanza dei totali
- Decidere se mantenere sia i totali aggregati (`total_price_net`/`total_price_with_tax`) sia i parziali (`products_total_*`, `shipping_total_*`), o solo uno dei due gruppi.
- Se si rimuove un gruppo: verificare tutti i consumer interni (PDF, export, corrispettivi) che potrebbero già leggere quei campi.

## Step 10 — Valutare `includes_shipping`
- Verificare se esiste un caso reale in cui `shipping` è valorizzato ma il documento non lo deve includere.
- Se no: rimuovere il campo e derivare dalla presenza di `shipping`.

---
Note di processo: aggiornare la documentazione/piano solo a fine step, nessun commit automatico, checkpoint esplicito prima di ogni migrazione Alembic e prima di ogni cambio di contratto di risposta consumato dal FE.
