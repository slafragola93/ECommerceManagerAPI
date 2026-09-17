# Promemoria — Criticità da analisi progetto (2026-09-14)

> Generato da analisi read-only dell'intero backend (nessun codice toccato in quella sessione).
> Da riprendere dopo il lavoro in corso su fatturazione.

---

## 🔴 Priorità alta — bloccanti

- [x] ~~**Test suite bloccata al 100%.**~~ **RISOLTO (verificato 2026-09-17).** `address_factory.py` ora importa correttamente (`from datetime import datetime`). Suite completa rilanciata oggi: **755 passed, 8 skipped, 0 failed** in 46s — collection pulita, nessun errore, anche i 25 fallimenti originari risultano rientrati. Non è chiaro in quale commit esatto sia stato risolto (probabilmente `2a8f757`, che ha toccato lo stesso file) — il promemoria non era mai stato aggiornato di conseguenza.

- [x] ~~**Debug code attivo in produzione**~~ **RISOLTO (verificato 2026-09-17).** Rimosso già ieri nel commit `764fad9` (16/09) — nessun riferimento a `debug.log` resta in `fatturapa_validator.py`. Eliminato oggi anche il file residuo `.cursor/debug.log` (125KB, mai committato — già in `.gitignore` — conteneva dati fiscali di validazioni fino al 15/09, non più scritto dal codice).

---

## 🟠 Sicurezza — da rivedere

- [ ] Endpoint "Admin only" in `src/main.py` **senza alcuna auth reale**: `DELETE /api/v1/cache`, `POST /api/v1/cache/reset`, `GET /api/v1/cache/stats`, `/metrics`. Aggiungere dependency di autenticazione/autorizzazione.
- [ ] CORS incoerente in `src/main.py`:
  - lista `origins` (righe ~342-352) definita ma mai usata (dead code);
  - handler globale `OPTIONS /{full_path:path}` (riga ~697) risponde `Access-Control-Allow-Origin: "*"` **+** `Access-Control-Allow-Credentials: "true"` — combo che i browser rifiutano ed è disallineata dalla `CORSMiddleware` reale (che whitelista solo 4 origin).
- [ ] 64 blocchi `except Exception`/`except:` silenziosi in 32 file (18 solo in `preventivo_service.py`) — rischio errori mascherati. Da rivedere almeno nei path critici (fatturazione, pagamenti, spedizioni).
- [ ] `requirements.txt` con versioni datate (FastAPI 0.110.1, starlette 0.37.2, cryptography 42.0.5, python-jose 3.3.0, PyYAML 6.0.1). Girare `pip-audit` o `safety check`, priorità su `python-jose`/`cryptography` (reggono il JWT).

---

## 🟡 Manutenibilità / architettura

- [ ] File monolitici da valutare per uno split: `fatturapa_validator.py` (1993 righe), `preventivo_service.py` (1798 righe), `main.py` (842 righe — spostare endpoint cache/metrics/health in un router dedicato).
- [ ] Doppio meccanismo di startup in `main.py`: `lifespan` (moderno) + `@app.on_event("startup")` deprecato che chiama `Base.metadata.create_all(bind=engine)` ad ogni avvio insieme ad Alembic → rischio drift schema/migration. Valutare rimozione del `create_all` a favore delle sole migration.
- [ ] Cartella `.git` orfana in `src/repository/.git` (non è un submodule, nessun `.gitmodules`). Non rompe nulla ma è fuorviante — valutare rimozione.

---

## 🧪 Test da chiarire (una volta sbloccata la suite)

> **Aggiornamento 2026-09-17**: la suite completa passa (755 passed, 8 skipped, 0 failed). I punti sotto risultavano tutti falliti nell'analisi del 14/09; oggi i test citati passano, ma non è stato verificato *come* siano stati risolti (fix del bug reale vs. test riallineato) — lasciati come promemoria da controllare con calma, specialmente quello sul calcolo resi/NC (area fiscale).

- [ ] `tests/unit/services/test_fiscal_document_create_return.py` — 3 test falliscono su calcolo resi/NC (`returns_net == 0` inatteso, `shipping_returns` vuoto). **Da verificare con attenzione**: non è chiaro se sia test disallineato o regressione reale nel calcolo dei resi — area fiscale, merita un check mirato. *(oggi passa: da confermare se il calcolo è stato corretto o solo il test)*
- [ ] Drift path endpoint nei test vs router reali:
  - `test_shippings_multi.py` chiama `/api/v1/shippings/multi-shipment`, il router espone `/api/v1/shippings/create-multi-shipments` → 405.
  - `test_sync_prestashop.py` si aspetta 202, riceve 404 (stesso tipo di drift).
  *(oggi passa: verificare se il router o il test sono stati allineati)*
- [ ] Fixture disallineate: `fake_carrier_factory` chiamato con keyword arg non più accettato dalla factory reale (`test_shippings_create.py`). *(oggi passa)*
- [ ] `test_fiscal_document_export_soft.py::test_partial_export_returns_zip_with_scarti` — `RuntimeError: EventBus has not been initialised` nel fixture di test (l'EventBus viene inizializzato solo dal `lifespan` reale, non nel setup unitario). *(oggi passa)*
- [ ] Test "scheletro"/TODO mai completati (es. `test_login_success`, commento esplicito "skeleton" senza seed utente) — da completare o rimuovere se obsoleti. *(non riverificato oggi: uno "skeleton test" può passare pur non testando nulla di reale)*
- [ ] `test_categories.py` (duplicate-name) — sembra soffrire di stato condiviso tra test più che di un bug applicativo; verificare isolamento fixture/DB tra i test. *(oggi passa)*

---

## ✅ Cose verificate OK (nessuna azione)

- Alembic: singola head, 87 migration, nessun conflitto.
- Nessuna credenziale hardcoded trovata in `src/`.
- Nessuna evidenza di SQL injection via query raw con f-string.
- File sensibili (`.env`, `.env.backup.*`, `test.db`, `debug-*.log`) correttamente esclusi da git.
- Modifiche in working tree su schema/serializer fatture (omissione campi solo-NC) coerenti e pulite.

---

*Riferimento: analisi completa discussa in chat il 2026-09-14, nessun file toccato durante l'analisi stessa.*
