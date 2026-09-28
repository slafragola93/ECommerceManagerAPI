# Staging — valutazione worker e database

Documento di analisi (2026-09-25). **Nessuna modifica al codice**: solo fattibilità e piano.

Fonti: [`DEPLOY_AMBIENTE_TEST.md`](DEPLOY_AMBIENTE_TEST.md), [`deploy-environment-elettronew_1.md`](deploy-environment-elettronew_1.md), codice attuale (`src/main.py`, `src/database.py`, sync, SSE, modelli).

Volumi di riferimento: **~600k ordini**, **~600k clienti**, **~1,2M address**, crescita ~400 ordini/giorno.

---

## In sintesi

| Domanda | Risposta |
|---|---|
| Due worker (esterni vs operatori)? | **Sì come due processi con ruoli diversi.** **No** come `uvicorn --workers 2`. |
| MariaDB o PostgreSQL al posto di MySQL 8? | **No per il primo staging.** Restare su **MySQL 8**. |
| MariaDB **e** PostgreSQL insieme? | **No.** Un solo motore. |
| Cosa fare al go-live test | 1 processo Uvicorn, MySQL 8, Redis 7, Nginx — come il runbook. |
| Lo stack dei runbook è pianificato correttamente? | **Sì, per come è scritta l’app oggi.** Non è lo stack ideale in astratto: è quello allineato al codice. |

I volumi non giustificano un cambio di database. Il collo di bottiglia è l’app (job nel processo HTTP, sync in RAM, indici mancanti), non il brand del motore.

---

## 1. Due worker: esterni vs operatori

### 1.1 Cosa chiedono i runbook

Entrambi i documenti dicono **1 solo worker Uvicorn**. Motivo: i job partono nel `lifespan` di **ogni** processo.

`run_prod.ps1` con `--workers 4` è esplicitamente sbagliato: duplica POOL/SDI/tracking e spezza l’SSE.

### 1.2 Cosa fa oggi il codice

Nel `lifespan` di `src/main.py` partono quattro loop:

| Job | Flag `.env` | Default |
|---|---|---|
| Sync stati ordine PrestaShop | **nessuno** (`enabled=True` fisso) | Sempre acceso |
| Polling tracking corrieri | `TRACKING_POLLING_ENABLED` | `true` |
| Sync POOL FatturaPA | `FATTURAPA_POOL_SYNC_ENABLED` | `true` |
| Sync eventi SDI | `FATTURAPA_SDI_EVENTS_SYNC_ENABLED` | `true` |

Altri vincoli nello stesso processo:

- **SSE** (`SseFanoutService`): code in memoria, non condivise tra processi
- **EventBus**: in-process
- **Rate-limit tracking**: dict in RAM
- **Sync PrestaShop** (`POST /api/v1/sync/...`): `BackgroundTasks` nel processo che ha ricevuto l’HTTP
- **Engine SQLAlchemy**: `create_engine(url)` senza `pool_pre_ping` / `pool_recycle` / `pool_size`

### 1.3 `uvicorn --workers 2` — non farlo

Due processi **identici**, non due ruoli.

| Effetto | Perché è un problema |
|---|---|
| Ogni processo riavvia i 4 job | Polling doppio verso FatturaPA, SDI, corrieri, PrestaShop |
| SSE e EventBus per-processo | Il browser sul worker A non vede eventi del worker B |
| Nessun lock distribuito | `order_states_sync` non si può nemmeno spegnere |
| Sync HTTP dove cade il load-balancer | Lavoro pesante imprevedibile |

Non è isolamento: è **duplicazione + eventi persi**.

### 1.4 Cosa ha senso: due processi con ruoli diversi

Stesso codice, stesso DB, stesso Redis, **env e porta diversi**.

| Processo | Porta | Ruolo | Job | Chi lo usa |
|---|---|---|---|---|
| `elettronew-api` | 8000 | Operatori (FE) | **tutti OFF** | login, ordini, fatture, PDF, SSE |
| `elettronew-worker` | 8001 (solo rete interna) | Servizi esterni | **tutti ON** | polling +, se instradato, `/api/v1/sync` |

Nginx: UI → `:8000`. Eventuale `/api/v1/sync*` → `:8001`.

Un crash/OOM/ban API sul worker non abbatte gli operatori. Un restart dell’API non interrompe un sync in corso.

### 1.5 Perché oggi non è plug-and-play

1. `order_states_sync` è sempre acceso — un secondo processo lo avvierebbe comunque.
2. I sync “lanciati dall’operatore” sono HTTP, non job. Senza routing Nginx (o coda), il full-sync PrestaShop torna sull’API operatori.
3. Il tracking si aggiorna sul worker; il browser ascolta sull’API. Senza Redis pub/sub l’SSE non arriva.
4. Due processi = due pool DB. Va ricalcolato `max_connections`.
5. Senza lock Redis, un flag sbagliato raddoppia i job.

### 1.6 Cosa isola (e cosa no)

**Separa:** polling, hang verso FatturaPA/corrieri, CPU di un full-sync (se gira sul worker).

**Non separa:** query lente, lock InnoDB, Redis, disco `media/`. Operatori e worker **condividono il DB**.

Un export/PDF pesante resta sull’API (è lavoro UI): se non pagina, satura comunque gli operatori.

### 1.7 Decisione worker

| Opzione | Primo staging | Note |
|---|---|---|
| `uvicorn --workers 2` sullo stesso servizio | **No** | Mai, finché i job restano nel `lifespan` |
| 1 processo, job esterni a `false` | **Sì — go-live** | Come `DEPLOY_AMBIENTE_TEST.md` |
| 2 unit systemd `api` + `worker` | Sì, dopo prep | Fase 2 del piano |
| Worker senza HTTP + coda | Target pulito | Fase 3, non prerequisito |

---

## 2. Database: MySQL 8 vs MariaDB vs PostgreSQL

### 2.1 I volumi non chiedono un cambio di motore

600k / 600k / 1,2M è un dataset **medio**. MySQL 8, MariaDB e PostgreSQL lo reggono se indicizzati.

Crescita ~400 ordini/giorno ≈ 145k ordini/anno → in 3 anni ~1M ordini. Ancora nella stessa classe.

Il rischio non è “MySQL 8 non scala a 1M righe”. È:

- sync che carica tutti gli `id_origin` in RAM
- `LIKE '%mario%'` (nessun indice usabile)
- indici assenti su colonne usate dal sync
- 1 processo che fa anche PDF/export
- `mysqldump` lento su dump grandi

### 2.2 Non usare MariaDB e PostgreSQL insieme

Due motori, due backup, due dialetti, dual-write. Complessità enorme, zero beneficio per questo gestionale.

### 2.3 MySQL 8 — restare (raccomandato)

L’app è scritta per questo:

- URL `mysql+pymysql://...` in `src/database.py` e `alembic/env.py`
- Dump/restore del runbook
- SQL nativo: `SET FOREIGN_KEY_CHECKS`, `INSERT IGNORE`, `ON DUPLICATE KEY UPDATE`, `SHOW TABLES`
- `func.year(...)` (numerazione documenti), `func.convert_tz(...)` (corrispettivi)
- Concat stringhe con `+` in `QueryUtils` (su PostgreSQL `+` è aritmetico)
- Migration generate con `sqlalchemy.dialects.mysql`
- Boolean su TINYINT; collation `utf8mb4_0900_ai_ci` in alcune tabelle

Buffer pool 4–8 GB e **indici** contano più del nome del motore.

### 2.4 MariaDB — sembra uguale, non è drop-in

| Punto | Impatto |
|---|---|
| Collation `utf8mb4_0900_ai_ci` | **Non esiste** su MariaDB. Dump MySQL 8 può fallire o cambiare ordinamenti |
| PyMySQL | Di solito ok, da testare |
| `FOREIGN_KEY_CHECKS` / `INSERT IGNORE` | Compatibili |
| Dump del runbook | Va **convertito**, non è un restore cieco |
| Vantaggio a 1–2M righe | Nessuno rilevante vs MySQL 8 |

Fattibile in 1–2 settimane di prove su dump reale. Utile **solo** se l’hosting non offre MySQL 8.

### 2.5 PostgreSQL — motore solido, migrazione cara

Meglio in astratto (concorrenza, JSON, window function, full-text). Su **questo** repo è un progetto, non uno switch.

| Accoppiamento | Cosa rompe |
|---|---|
| Driver | Serve `psycopg`; sparisce PyMySQL |
| URL + Alembic + `scripts/` | Tutti i connection string |
| SQL raw in `prestashop_service` | `SET FOREIGN_KEY_CHECKS`, bind tuple, insert batch |
| `func.year` / `func.convert_tz` | Errori silenziosi su documenti e corrispettivi |
| `+` sulle stringhe | Ricerche clienti sbagliate |
| ENUM / BOOLEAN | TINYINT vs `boolean` |
| Catena Alembic | **Già non replayable da zero** (serve `create_all` + `stamp`) |
| Dump | `mysqldump` non si importa; serve `pgloader` / ETL |

Stima: **3–6 settimane** + ambiente parallelo. Non sta sul path del primo staging.

### 2.6 Dove farà male (qualsiasi motore)

**Indici mancanti nei modelli:**

| Colonna | Indice oggi | Usata per |
|---|---|---|
| `customers.id_origin` | **No** | Sync (`MAX`, `IN`) |
| `addresses.id_origin` | **No** | Sync su 1,2M righe |
| `orders.date_add` | **No** | Filtri data, `func.year(...)` |
| `orders.id_order_state` | Non esplicito | Liste per stato |

A 1,2M address, `SELECT id_origin FROM addresses WHERE id_origin IS NOT NULL` è full scan + risultato enorme in RAM.

**Altri punti:**

- Sync PrestaShop fa `fetchall()` di tutte le origini → primo candidato OOM
- Ricerca operatori `LIKE '%x%'` → table scan a 600k clienti
- `func.year(date_add)` non usa l’indice (ok sui documenti/anno, da non copiare sulle tabelle grosse)
- Integer PK 32 bit: ~2,1 miliardi — non è un rischio in questa decade
- `order_details` (tipicamente 2–5× gli ordini) e XML/audit pesano più del “numero ordini”

### 2.7 Decisione database

| Scelta | Quando | Quando no |
|---|---|---|
| **MySQL 8** | Staging e primo prod | — |
| **MariaDB** | L’host non dà MySQL 8 | “Tanto è uguale” / dump senza conversione |
| **PostgreSQL** | Progetto dedicato, dopo misure reali | Primo deploy o “i dati sono tanti” |
| **Tutti e due** | Mai | — |

Riaprire PostgreSQL tra 6–12 mesi solo se le slow query / report lo chiedono. Non per il row count da solo.

---

## 3. Piano

### Fase 0 — primo deploy staging (ora)

Allinearsi a [`DEPLOY_AMBIENTE_TEST.md`](DEPLOY_AMBIENTE_TEST.md):

1. Linux + Python 3.11 + **1 worker** + **MySQL 8** + Redis 7 + Nginx/TLS
2. Dump popolato + `alembic upgrade head`, **oppure** DB vuoto: `create_all` + `alembic stamp` (§4a)
3. Job esterni **spenti** se le key sono di produzione (`FATTURAPA_*`, `TRACKING_POLLING_ENABLED=false`)
4. Ricordare: **order state sync resta acceso** (nessun flag)
5. CORS con origin reale del FE (`src/main.py` è hardcoded su localhost)
6. Health: `GET /api/v1/monitoring/health` — **`GET /health` non esiste**
7. Non usare `run_prod.ps1` così com’è
8. Non creare `fatture_download/` (XML in DB dal 2026-09-21). Il file `deploy-environment-elettronew_1.md` su questo punto è obsoleto

**Non fare al go-live:** secondo worker, MariaDB, PostgreSQL, Celery, Gunicorn.

### Fase 1 — hardening su MySQL 8 (prima di isolare i processi)

1. Indici: `id_origin` su `customers` e `addresses`; valutare `(id_store, id_origin)`; `orders.date_add`
2. Pool: `pool_pre_ping=True`, `pool_recycle=1800`, `pool_size` / `max_overflow` espliciti
3. Flag anche per `order_states_sync`
4. Misure: slow query log, tempo liste clienti/ordini, RAM durante un sync incrementale
5. Backup: tempo reale di dump **e restore** sul volume di test
6. Cap alle liste/export (già 5000 sui fiscal)

Senza questi numeri, “passiamo a PostgreSQL perché scala” è una scommessa.

### Fase 2 — isolamento api / worker

1. Env `PROCESS_ROLE=api|worker` (o equivalenti)
2. Flag su **tutti** i job
3. Redis pub/sub per SSE tracking
4. Lock Redis sui loop (SET NX + TTL)
5. Nginx: UI → `:8000`; `/api/v1/sync` → `:8001`; SSE sull’API
6. Due unit systemd, stessi `.env` tranne ruolo e porta
7. Pool DB ricalcolato per 2 processi
8. Health distinto: API “operatori ok”, worker “job vivi”

Finché i sync restano `BackgroundTasks` HTTP, **instradare `/sync` sul worker** è il minimo. Altrimenti si isolano solo i polling.

### Fase 3 — solo se Fase 2 non basta

Entrypoint `python -m src.worker` senza HTTP. I `POST /sync` **accodano** invece di lanciare task nel processo. Celery/ARQ è un’opzione, non un obbligo. Oggi i runbook dicono correttamente che Celery **non serve**.

---

## 4. Backlog rischi (motore-indipendenti)

1. Sync che materializza tutti gli `id_origin` in RAM
2. SSE e job legati al processo HTTP
3. Catena Alembic non bootstrapabile da zero
4. CORS hardcoded — senza patch il FE di test non parla con l’API
5. Crescita `order_details` + `audit_logs` + XML in riga: disco e backup prima del conteggio ordini
6. Directory `media/` piatte se immagini/etichette esplodono

---

## 5. Perché quelle opzioni non sono utili

Il punto non è “sono tecnologie brutte”. È che **non risolvono il problema che hai**, e in alcuni casi lo peggiorano. Il problema vero è: *un solo processo fa sia gli operatori sia i servizi esterni, e il DB è già MySQL 8*.

### 5.1 `uvicorn --workers 2` — non isola, clona

L’idea (“due processi, se uno va in crisi l’altro resta su”) è giusta. Il comando sbagliato.

Uvicorn con `--workers 2` non dice “questo fa i corrieri, quest’altro fa il gestionale”. Dice: **lancia due copie identiche della stessa app**. Ogni copia, all’avvio, esegue lo stesso `lifespan`: stessi 4 job, stesso EventBus, stesso SSE in RAM.

Effetto pratico:

- FatturaPA e i corrieri vengono interrogati **due volte** (rischio rate-limit, dati doppi, lock strani).
- L’operatore si collega a una copia; il tracking si aggiorna sull’altra → **il FE non vede l’evento**.
- Se il sync PrestaShop scoppia, può esplodere **qualsiasi** delle due copie, anche quella su cui sta lavorando qualcuno.

Non è “operatori al sicuro”. È “stesso rischio, due volte, più i bug”.

L’opzione utile è un’altra: **due servizi systemd con env diversi** (API senza job, worker con i job). Stesso codice, ruoli opposti. Quello sì isola. Non è pronto oggi perché manca il flag su `order_states_sync` e l’SSE non attraversa i processi.

### 5.2 MariaDB al posto di MySQL 8 — cambio senza guadagno

MariaDB e MySQL si assomigliano, ma **non sono lo stesso prodotto**. L’app e i dump sono tarati su MySQL 8 (`utf8mb4_0900_ai_ci`, `INSERT IGNORE`, `FOREIGN_KEY_CHECKS`, PyMySQL).

Cosa **non** ottieni passandoci:

- Non diventa più veloce su 600k/1,2M righe. A questi numeri i due motori sono equivalenti.
- Non isola operatori e sync. Il DB resta **uno**, condiviso.
- Non toglie i full scan (`id_origin` senza indice, `LIKE '%mario%'`).

Cosa **rischi**:

- Un dump MySQL 8 può non importarsi (collation che MariaDB non ha).
- Ordinamenti e confronti su email/nomi possono cambiare in silenzio.
- Giorni spesi a convertire e testare, zero beneficio sul go-live.

Diventa utile solo se **l’host non ti dà MySQL 8**. Non perché MariaDB sia “meglio per i volumi”.

### 5.3 PostgreSQL — utile in teoria, inutile *adesso*

PostgreSQL è un ottimo motore. Su un’app **nuova** lo sceglierei volentieri. Qui no, per un motivo semplice: **il dolore non è il motore**.

A 600k ordini e 1,2M address MySQL 8 è largamente sufficiente. Quello che farà lenta l’app è:

- sync che tira in RAM tutti gli `id_origin`;
- ricerche `LIKE '%…%'`;
- indici assenti;
- un processo solo che fa anche PDF/export.

PostgreSQL **non sistema nessuno di questi punti** da solo. Li ritrovi identici, più 3–6 settimane di riscrittura SQL/Alembic/dump.

Sarebbe un’opzione utile se, **dopo** aver misurato in staging, vedessi query che MySQL non riesce a pianificare bene, o report pesantissimi. Oggi stai ancora accendendo l’ambiente: cambieresti il pezzo che già funziona, lasciando rotto quello che fa male.

### 5.4 MariaDB **e** PostgreSQL insieme — doppio lavoro, zero isolamento

Due database per la stessa app significa: due backup, due dialetti, due set di indici, e il problema di tenere i dati allineati.

Non ottieni “uno per gli esterni e uno per gli operatori”: un ordine deve stare in **un** posto. Se li spezzi, ti inventi una sincronizzazione tra motori — più fragile del singolo MySQL.

Per un gestionale è un anti-pattern. Si sceglie **un** RDBMS.

### 5.5 Il filo comune

Tutte e quattro le opzioni sembrano “più robuste”. In realtà spostano il pezzo sbagliato.

| Opzione | Sembrerebbe fare | In questa app fa |
|---|---|---|
| `--workers 2` | Isolare i carichi | Clonare i job e rompere l’SSE |
| MariaDB | DB più adatto / più libero | Stesso MySQL, con dump da convertire |
| PostgreSQL | Scalare i grandi volumi | Mesi di migrazione, stessi buchi applicativi |
| Tutti e due i DB | Separare responsabilità | Due sistemi da tenere uguali |

Quello che *sarebbe* utile, in ordine:

1. **MySQL 8 + 1 worker**, come il runbook — per accendere staging.
2. **Indici e pool** — per i 600k/1,2M.
3. **Due processi con ruoli diversi** — per proteggere gli operatori dai servizi esterni.

Le altre strade non sono “vietate per sempre”. Sono **le ultime da prendere**, non le prime.

---

## 6. Lo stack attuale è pianificato correttamente?

**Sì, per come è scritta l’app oggi lo stack dei runbook è quello giusto.** Non è “lo stack ideale in astratto”: è quello allineato al codice, e per il primo staging è la scelta corretta.

### 6.1 Cosa è pianificato bene

| Pezzo | Perché è coerente |
|---|---|
| Linux + Python 3.11 + Uvicorn | È il runtime reale (`Dockerfile`, FastAPI 0.110). Windows resta solo dev. |
| **1 worker** | I job e l’SSE vivono nel processo. Non è un limite inventato, è un vincolo del codice. |
| **MySQL 8** + PyMySQL | Tutto (Alembic, dump, SQL raw) è MySQL. Cambiare ora sarebbe un progetto, non un deploy. |
| **Redis 7** hybrid | Cache e lock già previsti; senza Redis degradi a sola memoria. |
| Nginx + TLS + SSE (`proxy_buffering off`) | Ingresso e stream sono pensati. |
| systemd | Un processo da tenere su dopo crash/reboot. |
| Niente Celery / Gunicorn / PG / S3 | Oggi non servono: i job sono in-process, i file stanno su disco. |

Il profilo di carico dei doc (~10 utenti, ~400 ordini/giorno, anagrafica grande) è letto bene: **non è un problema di CPU da traffico**, è volume dati + picchi nel processo unico (PDF, sync, export). 4 vCPU / 8–16 GB / SSD è dimensionamento sensato.

### 6.2 Cosa è “corretto ora”, non “corretto per sempre”

Lo stack **non** isola operatori e servizi esterni. È una scelta consapevole: il codice non è ancora spezzabile senza prep. Il piano “1 processo al go-live → due ruoli dopo” è la sequenza giusta, non un buco.

Stesso discorso sul DB: MySQL 8 è corretto **per questo repo e questi volumi**. Non è un voto eterno contro PostgreSQL.

### 6.3 Dettagli da non copiare alla cieca

Piccoli disallineamenti tra i due file, non sullo stack in sé:

- Health vero: `GET /api/v1/monitoring/health`. `GET /health` nel Dockerfile / nel doc “elettronew_1” è sbagliato.
- `fatture_download/` è superato: XML in DB. Il runbook test ha ragione.
- `run_prod.ps1` (`--workers 4`) **non** fa parte dello stack pianificato: è un residuo da non usare.
- CORS ancora su localhost: va toccato prima che il FE di test funzioni.
- Alembic da zero non regge: dump popolato, oppure `create_all` + `stamp`.

### 6.4 In una frase

Sì — Linux, Python 3.11, Uvicorn 1 worker, MySQL 8, Redis 7, Nginx. È lo stack minimo che l’app sa far girare. Le cose da migliorare (indici, pool, poi api/worker) stanno **sopra** questo stack, non al posto di esso.

---

## 7. Riferimenti

| File | Ruolo |
|---|---|
| [`DEPLOY_AMBIENTE_TEST.md`](DEPLOY_AMBIENTE_TEST.md) | Runbook operativo staging (fonte per il go-live) |
| [`deploy-environment-elettronew_1.md`](deploy-environment-elettronew_1.md) | Stack e dimensionamento; su `fatture_download/` e `GET /health` è superato |
| `src/main.py` | Lifespan, job, CORS |
| `src/database.py` | Engine MySQL, nessun pool tuning |
| `src/events/sse/sse_fanout_service.py` | SSE in memoria |
| `src/routers/sync.py` | Sync PrestaShop via `BackgroundTasks` |
