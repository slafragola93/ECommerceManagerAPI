Sistema il generatore di note di credito XML FatturaPA (`TipoDocumento = TD04`, schema v1.2). Ci sono un bug da correggere e alcune buone pratiche da un sistema di riferimento attualmente in uso da replicare — ma NON tutto quel sistema va copiato, ci sono anche due difetti da NON riprodurre. Dettagli sotto.

## 1. Bug da correggere: data di scadenza pagamento calcolata sul documento sbagliato

Quando la nota di credito è collegata a una fattura precedente tramite `DatiFattureCollegate`, il campo `DatiPagamento/DettaglioPagamento/DataScadenzaPagamento` viene oggi calcolato usando la data della fattura originale collegata (`DatiFattureCollegate/Data`) invece della data della nota di credito stessa (`DatiGeneraliDocumento/Data`). Risultato: la scadenza riportata cade PRIMA della data di emissione della nota di credito (incoerenza logica; non causa scarto XSD/SdI ma genera dati errati lato riconciliazione/contabilità di chi riceve il file).

Caso di regressione reale: `IT08632861210_000003.xml` — `Data = 2026-07-22`, `DatiFattureCollegate/Data = 2026-04-17` (fattura n.13), `DataScadenzaPagamento` generata = `2026-05-17` (= 17/04 + 30gg, calcolata sul documento sbagliato).

**Fix:**
- Disaccoppia completamente il calcolo di `DataScadenzaPagamento` da `DatiFattureCollegate`: quest'ultimo deve essere letto SOLO per popolare il riferimento incrociato (tracciabilità), mai per derivare altre date del documento corrente.
- La scadenza, se presente, deve sempre basarsi su `DatiGeneraliDocumento/Data` del documento che si sta generando in quel momento.
- Per i TD04 in particolare, decidi esplicitamente (con un flag/config, non un comportamento implicito) tra:
  - **Opzione A**: la nota di credito genera un rimborso/compensazione con termine reale → calcolare `DataScadenzaPagamento = Data (nota di credito) + giorni_termine_pagamento`.
  - **Opzione B**: la nota di credito è solo una rettifica/storno → omettere del tutto il blocco `DataScadenzaPagamento` (opzionale, come fa correttamente l'esempio del sistema attuale, vedi punto 2 sotto).
- Aggiungi un controllo di coerenza che segnali un warning se, per qualsiasi documento generato, `DataScadenzaPagamento < DatiGeneraliDocumento/Data`.

## 2. Buone pratiche da replicare, prese dall'esempio del sistema attualmente in uso (`ITIT08632861210_97327.xml`)

- **Nessuna `DataScadenzaPagamento` quando non necessaria**: quell'esempio omette del tutto il campo nel `DettaglioPagamento`, evitando il bug del punto 1. Replica questo comportamento come default per i TD04 che non generano un vero nuovo termine di pagamento (Opzione B sopra).
- **`CodiceDestinatario = "0000000"` sempre abbinato a `PECDestinatario` valorizzato quando il codice destinatario SdI non è noto**: se il sistema non conosce il codice a 7 caratteri del destinatario, deve verificare se è disponibile un indirizzo PEC del cliente e valorizzarlo, per garantire comunque il recapito da parte di SdI (invece di lasciare il documento semplicemente "in attesa" nell'area riservata). Verifica che questa logica sia applicata in modo sistematico ovunque venga usato `CodiceDestinatario = 0000000`.
- **Campi IBAN/IstitutoFinanziario inclusi solo quando pertinenti alla modalità di pagamento**: nell'esempio, con `ModalitaPagamento = MP08` (carta di pagamento) non vengono valorizzati `IBAN`/`IstitutoFinanziario` perché non servono per quella modalità. Aggiungi/verifica una regola esplicita nel generatore: valorizzare `IBAN`/`IstitutoFinanziario`/`ABI`/`CAB`/`BIC` solo se `ModalitaPagamento` è una modalità che li richiede (es. MP05 bonifico), altrimenti ometterli.
- **`CodiceFiscale` del Cedente coerente con la P.IVA**: per una società, `CodiceFiscale` deve normalmente coincidere con `IdFiscaleIVA/IdCodice` (11 cifre), non un valore arbitrario o un formato da persona fisica. Verifica che il generatore imposti sempre `CodiceFiscale = IdCodice` per il Cedente quando si tratta di una società con P.IVA italiana.
- **Campo `Arrotondamento` calcolato e valorizzato in `DatiGeneraliDocumento`**: verifica che il generatore calcoli sempre l'eventuale differenza di arrotondamento tra somma dei dettagli riga e imponibile/imposta totale, valorizzando `Arrotondamento` (anche a "0.00" quando non c'è differenza) invece di ometterlo silenziosamente.

## 3. Cose da NON replicare dal sistema attuale (difetti noti, non vanno copiati)

- **Nome file non conforme**: quell'esempio si chiama `ITIT08632861210_97327.xml`, con il prefisso Paese duplicato ("ITIT" invece di "IT"). Il nome file deve seguire la convenzione ufficiale `<IdPaese><IdCodice>_<ProgressivoInvio>.xml`, corrispondente esattamente ai valori di `IdTrasmittente` nell'header (qui sarebbe `IT08632861210_97327.xml`). Verifica/correggi la funzione di naming dei file nel nuovo sistema perché non riproduca questo bug — è un controllo che SdI esegue e un nome non conforme può causare lo scarto del file.
- **Assenza di `DatiFattureCollegate` nelle note di credito**: quell'esempio non riporta alcun riferimento alla fattura originale. Anche se lo schema XSD lo permette (campo opzionale), la guida ufficiale AdE raccomanda di valorizzarlo per tracciabilità, ed è sostanzialmente rilevante ai fini della validità fiscale della rettifica (art. 26 DPR 633/72 — la nota di variazione deve essere riconducibile alla fattura che rettifica). Il nuovo sistema deve continuare a valorizzare `DatiFattureCollegate` (numero e data della fattura originaria) per ogni TD04, indipendentemente dal fatto che l'esempio di riferimento non lo faccia.

## Verifica

- Rigenera un caso equivalente a `IT08632861210_000003.xml` (nota di credito collegata a una fattura precedente) e verifica che `DataScadenzaPagamento`, se presente, sia sempre >= alla `Data` della nota di credito.
- Verifica che le fatture ordinarie (TD01) continuino a calcolare correttamente la propria scadenza sulla propria data (comportamento già corretto, es. `IT08632861210_000020.xml`).
- Aggiungi test che verifichino: PEC valorizzata quando CodiceDestinatario = 0000000 e PEC nota; IBAN assente quando ModalitaPagamento non lo richiede; CodiceFiscale Cedente coincidente con P.IVA; Arrotondamento sempre calcolato; DatiFattureCollegate sempre presente nei TD04; nome file conforme alla convenzione (nessun prefisso Paese duplicato).
