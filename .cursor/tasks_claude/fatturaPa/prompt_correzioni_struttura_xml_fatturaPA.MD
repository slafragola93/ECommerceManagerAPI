Sistema la logica di generazione XML FatturaPA (schema v1.2, root `p:FatturaElettronica`) per correggere 2 gap strutturali che riguardano in particolare gli indirizzi esteri. Trova nel codebase la funzione/modulo che costruisce i blocchi `Sede` (usato sia per `CedentePrestatore` che per `CessionarioCommittente`, ed eventuale `RappresentanteFiscale`/`TerzoIntermediarioOSoggettoEmittente`) e applica le correzioni lì, in modo che valgano per qualsiasi parte, non solo per un caso specifico.

**Gap 1 — `NumeroCivico` non deve mai essere serializzato vuoto**
Il campo è opzionale (`minOccurs="0"`) ma se presente richiede almeno 1 carattere (pattern `{1,8}`). Attualmente, quando il numero civico è assente o vuoto, il generatore scrive comunque `<NumeroCivico />`, che non rispetta il pattern e causa scarto da parte del Sistema di Interscambio.
Fix: se il valore del numero civico è nullo/vuoto, l'elemento `NumeroCivico` non va incluso nell'XML (omissione completa del tag), non serializzato vuoto.

**Gap 2 — `Provincia` non va valorizzata per indirizzi esteri**
Il campo accetta solo 2 lettere maiuscole (pattern `[A-Z]{2}`, sigle provinciali italiane). Per gli indirizzi con `Nazione != "IT"` il generatore non deve scrivere l'elemento `Provincia` in nessun caso (nemmeno con il nome della città/regione estera) — va omesso interamente, coerentemente con le regole di compilazione FatturaPA per soggetti esteri.
Fix: condizionare la serializzazione di `Provincia` a `Nazione == "IT"`. Se `Nazione != "IT"`, il campo va sempre omesso indipendentemente dal valore presente nei dati anagrafici del cliente/fornitore.

**Gap 3 (minore, da valutare) — `CAP` per indirizzi esteri**
Le FAQ dell'Agenzia delle Entrate raccomandano di valorizzare `CAP` con il valore generico `"00000"` per indirizzi con `Nazione != "IT"`, riportando eventualmente il codice postale reale all'interno del campo `Indirizzo`. Attualmente il generatore scrive il CAP estero reale nel campo `CAP` (es. "75002" per un indirizzo francese) — è valido rispetto allo schema XSD (5 cifre) ma non segue la prassi raccomandata.
Fix: aggiungere un'opzione/flag per usare `"00000"` come CAP quando `Nazione != "IT"` (mantenendo comunque il valore reale disponibile altrove, es. concatenato in `Indirizzo`, se serve per altri usi). Se il team preferisce mantenere il CAP reale per motivi operativi, lasciare un commento esplicito nel codice che documenti la scelta consapevole rispetto alla raccomandazione AdE.

**Verifica**
- Aggiungi/aggiorna test che generano una fattura verso un cliente IT (Provincia valorizzata, CAP italiano) e una verso un cliente UE/extra-UE (es. Francia): verifica che per il caso estero `Provincia` sia assente nell'XML risultante e che `NumeroCivico` non compaia mai vuoto.
- Valida l'XML generato contro lo schema ufficiale `Schema_del_file_xml_FatturaPA_versione_1.2.xsd` (o versione in uso) per entrambi i casi.
- Usa come riferimento/regressione il file `IT08632861210_000020.xml` (fattura verso L'Oreal, Francia) che presenta entrambi i problemi: `<NumeroCivico />` vuoto nella Sede del Cedente e `Provincia = "Paris"` nella Sede del Cessionario.
