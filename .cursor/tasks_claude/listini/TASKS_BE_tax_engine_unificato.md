---
name: Tasks Backend — Persistenza IVA + Listini strutturati (FE fonte di verità)
overview: Il BE smette di calcolare i prezzi e diventa un livello di persistenza con validazione leggera di coerenza. VIES diventa una semplice aliquota anagrafica (is_vies + natura_code). Nessun endpoint dedicato VIES, nessun reference snapshot separato: il FE è l'unica fonte di calcolo, il campo unit_price_net non viene mai sovrascritto se non per azione esplicita dell'operatore.
status: pending
---

# Decisione architetturale (cambio rispetto a versione precedente)

Dopo analisi e discussione, si è deciso di **abbandonare l'approccio "BE motore di calcolo autoritativo con anchor + reference snapshot"** in favore di un modello più semplice:

- **Il FE è l'unica fonte di verità sul calcolo.** Calcola lordo/imponibile/totali e li invia già pronti nel payload, come faceva storicamente.
- **Il BE non ricalcola, persiste e valida leggermente.** Nessun `TaxPriceEngine` come motore che sovrascrive i valori ricevuti.
- **Nessuna colonna `ref_*` di reference snapshot.** Non serve: finché `unit_price_net` non viene mai sovrascritto a sproposito (disciplina lato FE, vedi file task FE), è esso stesso il valore di riferimento. Duplicarlo in una colonna separata sarebbe ridondante.
- **VIES resta solo un'aliquota** (`is_vies` + `natura_code`), nessun endpoint dedicato — questa parte non cambia rispetto alla decisione precedente.
- **Reversibilità naturale:** applicare VIES "mantenendo l'imponibile" e poi tornare all'aliquota standard "mantenendo l'imponibile" riporta esattamente al valore di partenza, perché il campo non sovrascritto (`unit_price_net`) non è mai stato perso. Questo elimina il bug originale (switch successivo che ricalcola da un valore già mutato) senza bisogno di reference dedicato.

**Perché si torna a questo modello:** l'approccio con `anchor` lato BE introduceva complessità difficile da seguire nella distinzione tra switch aliquota, modifica manuale prezzo e gestione sconti. Centralizzando il calcolo nel FE (in un solo punto, vedi file task FE) si ottiene la stessa garanzia di coerenza senza dover gestire più modalità/endpoint lato BE.

---

# Contesto Frontend (per allineamento — leggere prima di iniziare)

## Cosa farà il FE

- Userà un'unica funzione di calcolo centralizzata (`applyTaxChange`, estensione di `applyTaxChangeKeepGrossLine` già esistente in `shared/document-pricing`) per qualunque cambio aliquota, con due modalità esplicite scelte dall'operatore: `keep_net` (mantieni imponibile, ricalcola lordo) e `keep_gross` (mantieni lordo, ricalcola imponibile).
- Rimuoverà le formule IVA duplicate oggi presenti in `order-details-modal.component.ts`, `create-order.component.ts`, `return-details-modal.component.ts`, shipping — tutte devono convergere sulla funzione unica.
- Rimuoverà il flusso VIES dedicato (`applyViesExemption`, pulsanti separati): VIES sarà selezionabile come una qualunque aliquota dal dropdown standard, con scelta della modalità (`keep_net`/`keep_gross`) come per qualunque altro switch.
- Invierà sempre il payload completo già calcolato (`unit_price_net`, `unit_price_with_tax`, `total_price_net`, `total_price_with_tax`, `id_tax`, sconti) — il BE non si aspetta più solo `id_tax`.

## Modulo Listini — gestione codice natura (invariato rispetto a versione precedente)

Resta valida la parte su `Tax.natura_code`/`is_vies` per sostituire la propagazione via campo `note` (vedi BE-2 sotto) — questa parte della decisione architetturale non cambia.

---

# Tasks Backend

## BE-1 — Schema di persistenza riga ordine (validazione leggera, no calcolo)

**Dove:** `order_schema.py` (o equivalente), `order_detail_service.py`

**Cosa fare:**
- Lo schema di update riga accetta il payload completo già calcolato dal FE:
  ```python
  class OrderDetailUpdateSchema(BaseModel):
      product_qty: int
      id_tax: int
      unit_price_net: Decimal
      unit_price_with_tax: Decimal
      total_price_net: Decimal
      total_price_with_tax: Decimal
      reduction_percent: Decimal = 0
      reduction_amount: Decimal = 0
      note: str | None = None
      rda: str | None = None

      @field_validator("unit_price_net", "unit_price_with_tax", "total_price_net", "total_price_with_tax")
      @classmethod
      def non_negative(cls, v):
          if v < 0:
              raise ValueError("Il prezzo non può essere negativo")
          return v
  ```
- **Rimuovere ogni calcolo IVA dal service** (`_calculate_price_fields` o equivalente in `order_detail_service.py`): i valori ricevuti vengono persistiti così come sono, nessun ricalcolo lato BE.
- Analogo per spedizione (`shipping`), righe `create-order`, righe `return-details`.

**Acceptance:** salvando una riga con prezzi calcolati dal FE, i valori persistiti in DB corrispondono esattamente a quelli inviati (nessuna sovrascrittura silenziosa).

## BE-2 — `Tax.natura_code` + `Tax.is_vies` (invariato)

**Dove:** model `Tax`, migration, eventuale script di migrazione dati

**Cosa fare:**
- Aggiungere colonne `natura_code: str | None` e `is_vies: bool = False` al model `Tax`.
- Creare/identificare due record: aliquota VIES (`natura_code="N3.2"`, `is_vies=True`) e aliquota 0% generica (`is_vies=False`).
- Migrazione dati da `electronic_code` FE (se persistito) o popolamento manuale dei record esistenti — coordinarsi col FE sul set di codici validi (`ELECTRONIC_INVOICE_STATIC_DATA.Natura`).

**Acceptance:** query su `Tax` restituisce `natura_code` e `is_vies` per ogni aliquota; nessuna logica BE legge più il codice natura da `note`.

## BE-3 — `vies_status` derivato (invariato)

**Dove:** model `OrderDetail`/`Order`

**Cosa fare:**
```python
@property
def vies_status(self) -> str:
    return "eligible" if self.tax.is_vies else "not_eligible"
```
- Rimuovere ogni scrittura esplicita di `vies_status` da azioni dedicate.
- Rimuovere endpoint `/apply-vies-exemption`, `/revoke-vies-exemption` (o equivalenti) — VIES si applica/rimuove cambiando `id_tax` tramite l'update riga standard (BE-1).

**Acceptance:** impostando `id_tax` su un'aliquota con `is_vies=True`, `vies_status` risulta `eligible` senza chiamate aggiuntive.

## BE-4 — Validazione di coerenza leggera (guard rail, non calcolo)

**Dove:** `order_detail_service.py`, validatore Pydantic o check esplicito nel service

**Cosa fare:**
- Aggiungere un controllo a basso costo, **non bloccante per la logica di business ma protettivo contro errori grossolani**, prima di persistere:
  ```python
  expected_gross = unit_price_net * (1 + tax.percentage / 100)
  if abs(unit_price_with_tax - expected_gross) > TOLERANCE:  # es. 0.05€
      logger.warning(
          f"Incoerenza prezzo riga {detail_id}: atteso ~{expected_gross}, ricevuto {unit_price_with_tax}"
      )
      # decidere: solo warning, o 422 se la discrepanza è oltre una seconda soglia più ampia
  ```
- Obiettivo: non rifare il calcolo (il FE resta fonte di verità), solo intercettare casi palesemente incoerenti (es. bug FE, payload corrotto) prima che finiscano in un documento fiscale.
- Definire due soglie: una di warning (log, non blocca) e una di hard-stop (rifiuta il salvataggio) per discrepanze molto ampie — valori da concordare con il team.

**Acceptance:** un payload con lordo/imponibile palesemente incoerenti con l'aliquota dichiarata genera almeno un log di warning; discrepanze oltre soglia critica vengono rifiutate con errore esplicito.

## BE-5 — Audit minimo modifiche manuali

**Dove:** `order_detail_service.py` o modello `OrderDetail`

**Cosa fare:**
- Garantire che ogni update riga registri `updated_by`/timestamp (se non già presente) per tracciabilità — utile per capire a posteriori perché un prezzo è quello che è, dato che il BE non controlla più la coerenza del calcolo nel dettaglio.

**Acceptance:** ogni modifica riga è tracciabile con autore e timestamp.

## BE-6 — Sync PrestaShop: adattamento aliquota per paese (keep_gross fisso)

**Dove:** `src/services/ecommerce/ps_order_tax_adaptation.py`

**Decisione:** questo modulo resta ed è il **solo punto legittimo di calcolo IVA lato BE**. Il suo comportamento è `keep_gross` fisso e non configurabile, per una ragione di business chiara e documentata:

```python
# Il lordo è il prezzo pagato dal cliente su PrestaShop — immutabile.
# PS invia sempre aliquota 22% indipendentemente dal paese di consegna.
# Il BE adatta l'aliquota corretta per paese e ricalcola SOLO l'imponibile.
# Ancora: keep_gross (lordo fisso, imponibile ricalcolato).
```

**Cosa fare:**
- Mantenere la logica esistente di adattamento aliquota per paese.
- Aggiungere il commento esplicito sopra (o equivalente) per documentare il motivo del `keep_gross` fisso — evita che qualcuno in futuro lo "normalizzi" per allinearlo alla logica FE.
- Verificare che questo modulo non venga mai chiamato nel flusso operatore via FE — deve restare esclusivamente nel flusso di sync PS.

**Acceptance:** gli ordini sincronizzati da PS hanno sempre il lordo invariato rispetto al dato PS e l'imponibile adattato all'aliquota del paese di consegna.

## BE-7 — Endpoint switch aliquota massivo (tutte le righe ordine)

**Dove:** `order_service.py`, router ordini

**Decisione:** lo switch aliquota deve poter operare sia a livello di **singola riga** (già esistente, aggiornato in BE-1) sia **massivamente su tutte le righe dell'ordine** in un'unica chiamata, perché ordini diversi possono avere aliquote diverse e l'operatore deve poterle allineare tutte in una sola operazione.

**Cosa fare:**
- Aggiungere endpoint dedicato per lo switch massivo:
  ```http
  PATCH /api/v1/orders/{id_order}/recalculate-tax-bulk
  Content-Type: application/json

  {
    "id_tax": 42,
    "mode": "keep_net" | "keep_gross",
    "apply_to_shipping": true | false
  }
  ```
- Il BE itera su tutte le righe e la spedizione (se `apply_to_shipping=true`), ma **non ricalcola lui stesso** — delega il calcolo al FE o, in alternativa, chiama la stessa logica di `ps_order_tax_adaptation` solo se il flusso è interno e non operatore. Opzione preferita: il FE manda direttamente i prezzi già ricalcolati per ogni riga in un payload array, il BE persiste in transazione atomica.

  Payload alternativo (consigliato per coerenza con l'architettura FE fonte di verità):
  ```http
  PATCH /api/v1/orders/{id_order}/order-details/bulk-update
  Content-Type: application/json

  [
    { "id": 1, "id_tax": 42, "unit_price_net": 100.00, "unit_price_with_tax": 122.00, "total_price_net": 200.00, "total_price_with_tax": 244.00 },
    { "id": 2, "id_tax": 42, "unit_price_net": 50.00,  "unit_price_with_tax": 61.00,  "total_price_net": 50.00,  "total_price_with_tax": 61.00 }
  ]
  ```
  Il FE calcola tutto (usando `applyTaxChange` su ogni riga), poi invia il batch. Il BE persiste in transazione atomica e ricalcola i totali ordine al termine.

- **Transazione atomica:** o tutte le righe vengono aggiornate o nessuna — nessuno stato parziale.
- Dopo il bulk update, chiamare `recalculate_totals_for_order` per aggiornare i totali ordine.

**Acceptance:** un bulk update su ordine con 3 righe aggiorna tutte e 3 atomicamente; se una riga fallisce la validazione leggera (BE-4), l'intera operazione viene rifiutata.

## BE-8 — Pulizia codice obsoleto

**Dove:** `src/vies/exemption_calculation.py`, eventuali tracce di `TaxPriceEngine`/reference snapshot se già abbozzate

**Cosa fare:**
- Rimuovere `exemption_calculation.py` (o ridurlo a semplice passthrough se serve compatibilità import temporanea).
- Rimuovere eventuali migration/colonne `ref_*` se già create in una iterazione precedente non ancora rilasciata.

**Acceptance:** nessun modulo BE contiene logica di calcolo IVA per il flusso operatore via FE (escluso `ps_order_tax_adaptation.py` che è il solo caso legittimo).

## BE-9 — Documentazione da allineare

- README.md, `PROGRAMMA_BE_aliquote_vies.md`, `docs/FE_VIES_APPLY_EXEMPTION_BUTTON.md`, `BACKLOG_UNIFICATO.md` — aggiornare per riflettere: niente endpoint VIES dedicato, niente calcolo BE, FE fonte di verità.

---

# Note di coordinamento

- **BE-1 è bloccante per FE-1** del file frontend: il contratto di payload (completo, con prezzi calcolati) deve essere confermato prima che il FE consolidi la funzione di calcolo unica.
- **BE-2 è bloccante per FE-2** (Listini): il FE non può smettere di usare `note` come proxy del codice natura finché `natura_code` non è disponibile.
- **BE-4 (validazione leggera)** non blocca lo sviluppo FE — può essere implementata in parallelo o anche dopo il rilascio iniziale, è un guard rail aggiuntivo non un prerequisito di contratto.
- Nessuna diagnostica/backfill su ordini legacy necessaria (ambiente di sviluppo, dati di test).
