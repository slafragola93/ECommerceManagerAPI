# Ambiente di deploy — Elettronew API

Riassunto dello stack necessario per mettere in produzione il backend di Elettronew (FastAPI). Non è uno stack "Python + DB" generico: l'app ha vincoli precisi legati a come è scritta oggi (job in-process, cache Redis, file su disco, SSE).

## 1. Obbligatorio — senza questo l'app non gira

| Ruolo | Tecnologia | Note |
|---|---|---|
| Runtime | Linux + Python 3.11 | Il Dockerfile usa `python:3.11-slim`. Windows resta ambiente di sviluppo, non target di produzione. |
| App server ASGI | Uvicorn (`src.main:app`, porta 8000) | FastAPI 0.110. Niente Gunicorn nel repo, non serve. |
| Database | MySQL 8 (utf8mb4, InnoDB) | Driver PyMySQL. Non è nel docker-compose: va predisposto come servizio esterno. |
| Migrazioni | Alembic | `alembic upgrade head` a ogni deploy. |
| Cache | Redis 7 | `CACHE_BACKEND=hybrid` via `REDIS_URL`. Senza Redis, cache e lock/refresh ne risentono. |
| Disco persistente | `media/`, `logs/`, `fatture_download/` | PDF, loghi, etichette corrieri, XML FatturaPA. Non c'è S3: senza backup del volume si perdono i file. |
| Segreti | `.env` o secret manager | `SECRET_KEY` JWT, credenziali MySQL/Redis, API esterne. |

Librerie/pacchetti di sistema utili nell'immagine o sull'host: `curl` (per l'healthcheck `/health`), toolchain C (`gcc`, `g++`, `pkg-config`) se si builda da source, `libxml2`/`libxslt` (servono a `lxml` per l'XML FatturaPA/SDI). **Non serve Postgres** — `libpq-dev` nel Dockerfile è un residuo, il DB è solo MySQL. Per i PDF basta `fpdf2` + `pypdf`, niente wkhtmltopdf / LibreOffice / Chrome headless.

## 2. Ingresso in produzione (fortemente consigliato)

- **Reverse proxy + TLS**: Nginx (o Caddy) con certificato Let's Encrypt, che termina HTTPS e inoltra a `127.0.0.1:8000`.
- **Process manager**: systemd, oppure Docker Compose con `restart: unless-stopped`, per il riavvio automatico dopo crash/reboot.
- **Firewall**: esporre solo 80/443. Redis, MySQL, Grafana e Redis Commander non devono essere pubblici.
- **SSE** (`/api/v1/events/stream`): Nginx deve avere `proxy_buffering off;`, `proxy_read_timeout 3600s;`, `proxy_http_version 1.1;`.
- **CORS**: oggi è hardcoded su `localhost:4200` / `8082`. In produzione va allineato all'origine reale del frontend, altrimenti il browser blocca le chiamate.

## 3. Job e sync — attenzione, non c'è Celery

I job partono dentro il processo Uvicorn stesso (lifespan): sync stati ordine (orario), polling tracking corrieri, sync POOL FatturaPA, sync eventi SDI.

Questo significa:
- non servono Redis Queue, Celery, cron esterno o un worker dedicato;
- **va usato 1 solo worker Uvicorn** finché i job restano in-process — `run_prod.ps1` con `--workers 4` moltiplicherebbe i job (polling quadruplo) e romperebbe il fan-out SSE, che è in memoria per processo (più worker = eventi persi o duplicati tra client).

## 4. Osservabilità (prevista, ma opzionale in prod)

Il `docker-compose.yml` include Prometheus (`:9090`), Grafana (`:3000`) e Redis Commander (`:8081`, da tenere solo su rete interna, mai esposto). Il minimo operativo è log su file con rotazione + healthcheck su `GET /health`; Prometheus/Grafana sono utili ma non bloccanti per l'avvio.

## 5. Connettività in uscita necessaria

Il server deve poter raggiungere in HTTPS: PrestaShop (`PRESTASHOP_BASE_URL`), FatturaPA.com (upload SDI, POOL, notifiche), i corrieri (BRT / DHL / FedEx), eventualmente VIES (IVA UE) e l'SMTP per le mail. Senza queste uscite l'API parte comunque, ma sync, fatturazione e spedizioni falliscono.

## 6. Stack minimo vs completo

**Minimo funzionante**: Internet → Nginx (TLS, :443) → Uvicorn 1 worker (:8000) → MySQL 8 + Redis 7 → disco per `media/`, `logs/`, `fatture_download/`.

**Completo** (allineato al repo): minimo + Prometheus + Grafana (+ Redis Commander solo su rete interna).

**Non necessario oggi**: PostgreSQL, Mongo, Elasticsearch, Celery/RabbitMQ/Kafka, object storage S3, Node/PHP/Java sul server API, stack GPU/ML. Il frontend Angular è un deploy separato: sul server API basta CORS configurato correttamente + proxy.

## 7. Dimensionamento e hardening

### 7.1 Stima per il carico previsto (~10 utenti attivi, ~400 ordini/giorno, anagrafica clienti >500k, >500k ordini storici)

Il punto chiave è che questo profilo non è "CPU-bound": 10 utenti e 400 ordini/giorno sono un carico di concorrenza molto basso per un'app async come FastAPI/Uvicorn — anche con **1 solo worker** (vincolo del punto 3) non c'è rischio di saturazione da traffico. Il vincolo reale è il **volume dei dati storici** (indicizzazione, dimensione del DB, I/O su disco, backup), non il numero di richieste al secondo.

- **CPU**: 4 vCPU consigliati (contro il "pavimento" di 2 indicato in generale). Non servono per il traffico in sé, ma per assorbire i picchi sincroni che girano nel processo Uvicorn: generazione PDF (borderò, fatture), export/pandas su dataset che possono attingere a centinaia di migliaia di righe, sync POOL FatturaPA. Con 1 solo worker, questi picchi possono rallentare percepibilmente gli altri utenti se la CPU è risicata.
- **RAM**: 8–16 GB (contro i 4 GB "pavimento"). La stima va sopra il minimo generico per tre motivi: il buffer pool InnoDB di MySQL deve poter tenere in memoria il working set delle tabelle clienti/ordini (con oltre 500k+500k righe più le tabelle collegate — righe ordine, indirizzi, fatture, tracking — il dataset indicizzato è facilmente nell'ordine di qualche GB), Redis per la cache, e margine per eventuali query/export che caricano molti record in memoria via pandas senza streaming/paginazione (da verificare nel codice: se un export "tutti i clienti" o "tutti gli ordini" non pagina, può causare un picco improvviso di RAM).
- **Disco**: SSD (preferibile NVMe), non solo per lo spazio ma per le IOPS — con tabelle da 500k-1M+ righe indicizzate, un disco lento si sente soprattutto su ricerche/filtri e sui backup. Da ripensare la stima "40–80 GB" verso **100–150 GB** minimo, considerando: il DB che cresce nel tempo (~400 ordini/giorno ≈ 145.000 nuovi ordini/anno, più anagrafica clienti in crescita), `fatture_download/` con PDF+XML per ogni fattura (potenzialmente centinaia di migliaia di file: se le directory sono piatte per anno/mese conviene comunque organizzarle a sotto-cartelle per evitare cartelle con centinaia di migliaia di file, problema noto su molti filesystem), `media/`, `logs/`, e spazio per i backup locali temporanei prima dell'upload.
- **Indicizzazione MySQL**: a questi volumi diventa critica, non opzionale — indici su ciò che si filtra/ordina spesso (email/codice cliente, data ordine, stato ordine, `id_origin` da PrestaShop). Senza indici corretti, una tabella da 500k+ righe passa rapidamente da query istantanee a query di secondi.
- **Backup**: a questa scala un semplice `mysqldump` può diventare lento e bloccante; valutare backup fisici (es. Percona XtraBackup) o dump incrementali, e testare periodicamente i tempi di restore reali (non solo la riuscita del backup).
- **Da monitorare nel tempo**, non da risolvere subito: se la generazione PDF/pandas comincia a rallentare gli altri utenti mentre gira (essendo tutto nel processo Uvicorn singolo), valutare in futuro di spostare quelle operazioni pesanti fuori dal processo principale — oggi con questi volumi non è necessario, ma è il primo limite che si incontrerebbe crescendo.

### 7.2 Altri punti di hardening

- **MySQL**: backup giornalieri, utente dedicato, bind solo su rete privata.
- **Redis**: `requirepass` impostata, porta 6379 non pubblica, persistenza AOF/RDB se si usano lock/cache "calda".
- **Sequenza di deploy**: `pip install -r requirements.txt` → `alembic upgrade head` → seed RBAC se serve (`scripts/init_auth_data.py` / `setup_initial.py`) → restart Uvicorn.
- L'immagine Docker attuale (`--reload`, MySQL su `host.docker.internal`) è da sviluppo: per la produzione va tolto `--reload`, va usato 1 worker, e MySQL/Redis devono essere raggiungibili in rete privata.

## 8. Frontend (Angular 17)

Nota: questa sezione è basata su quanto è noto del progetto (Angular 17 + NgRx + Bootstrap 5/SCSS via template Velzon, servito come build statica dietro Nginx), non su un'analisi del repo frontend come quella fatta per il backend. I punti segnalati come "da verificare" vanno controllati sul repo reale prima del deploy.

- **Build**: Node.js/npm servono solo in fase di build (`ng build --configuration production`), non in produzione — l'output è una cartella di file statici (`dist/`). In produzione non serve un runtime Node sul server.
- **Serving**: i file statici possono essere serviti dallo stesso Nginx del backend (un server block/path dedicato), senza bisogno di un servizio applicativo separato.
- **Routing client-side**: essendo un'app Angular con routing lato client, Nginx deve fare fallback su `index.html` per le rotte non corrispondenti a un file reale (`try_files $uri $uri/ /index.html;`), altrimenti il refresh su una rotta interna (es. `/ordini/123`) restituisce 404.
- **URL API di produzione**: da verificare `environment.prod.ts` (o equivalente) — deve puntare al dominio/endpoint reale del backend in produzione, non a `localhost`. Da controllare anche altre chiavi/URL eventualmente hardcoded.
- **CORS**: il backend ha oggi CORS hardcoded su `localhost:4200`/`8082` (vedi punto 2) — va aggiornato con l'origine reale di produzione del frontend. Se FE e BE sono su domini/sottodomini diversi, il CORS va configurato anche per lo stream SSE.
- **Cache**: i bundle Angular hanno hash nel nome file, quindi si possono cachare in modo aggressivo (`Cache-Control` lungo); `index.html` invece va servito senza cache (o cache breve), altrimenti i client restano bloccati su una versione vecchia dopo un deploy.
- **HTTPS**: stesso certificato/dominio del backend se serviti insieme, oppure certificato dedicato se il frontend è su un sottodominio separato.
- **Da verificare nel repo reale**: comando di build esatto e eventuale script CI, variabili d'ambiente iniettate a build-time vs runtime, presenza di service worker/PWA, dimensione del bundle.

## 9. Processo di deploy — passo per passo

**Fase 0 — Preparazione server (una tantum)**
1. Provisioning host (minimo 2 vCPU / 4 GB, vedi punto 7).
2. Installare Python 3.11, Nginx, MySQL 8, Redis 7 (oppure puntare a servizi già esistenti sull'infrastruttura interna).
3. Creare il database MySQL dedicato (utf8mb4/InnoDB) con un utente applicativo a privilegi limitati (non root).
4. Configurare Redis con `requirepass` e bind solo su rete privata.
5. Creare le directory persistenti `media/`, `logs/`, `fatture_download/` con i permessi corretti e includerle nel piano di backup.
6. Configurare il firewall: solo 80/443 esposte pubblicamente.

**Fase 1 — Deploy backend**
1. Clonare il repo backend sul server.
2. Creare virtualenv, `pip install -r requirements.txt`.
3. Configurare `.env` con le credenziali reali (MySQL, Redis, `SECRET_KEY`, chiavi API esterne — PrestaShop, FatturaPA, corrieri).
4. Eseguire `alembic upgrade head`.
5. Seed dati iniziali se necessario (`scripts/init_auth_data.py` / `setup_initial.py` per RBAC).
6. Avviare Uvicorn con **1 worker** come servizio persistente (systemd, oppure Docker Compose con `restart: unless-stopped`).
7. Verificare `GET /health`.

**Fase 2 — Deploy frontend**
1. Configurare `environment.prod.ts` con l'URL reale dell'API di produzione (prima del build, non dopo).
2. Build di produzione: `ng build --configuration production` → cartella `dist/`.
3. Copiare il contenuto di `dist/` nel path servito da Nginx.

**Fase 3 — Reverse proxy e TLS end-to-end**
1. Configurare Nginx: backend su `/api` (o dominio/sottodominio dedicato), frontend su `/` con `try_files $uri $uri/ /index.html;`.
2. Impostazioni SSE per lo stream eventi (`proxy_buffering off;`, `proxy_read_timeout 3600s;`, `proxy_http_version 1.1;`).
3. Ottenere il certificato TLS (Let's Encrypt/Certbot o equivalente interno) e forzare HTTPS.
4. Aggiornare la configurazione CORS del backend con l'origine reale del frontend (non più `localhost`).

**Fase 4 — Verifica**
1. Smoke test end-to-end: login, creazione/visualizzazione ordine, generazione PDF, stream SSE attivo.
2. Verificare che le integrazioni esterne raggiungibili in questo ambiente rispondano (sync PrestaShop, FatturaPA, corrieri) — in staging, solo verso store/sandbox di test, non produzione reale.
3. Controllare log applicativi e l'healthcheck sotto carico minimo.

**Fase 5 — Deploy successivi (aggiornamenti, non il primo setup)**
1. Pull della nuova versione del codice (backend e/o frontend).
2. Se ci sono nuove migrazioni: `alembic upgrade head` (da confermare esplicitamente prima di eseguirla, non automatico).
3. Restart del servizio Uvicorn (systemd restart o equivalente).
4. Nuova build frontend e sostituzione dei file statici serviti da Nginx.
5. Smoke test rapido post-deploy (punto Fase 4).

Nota: poiché il server è gestito da un collega interno e non da Enrica, alcuni di questi passaggi (in particolare Fase 0 e l'accesso a `.env`/segreti) vanno coordinati direttamente con chi amministra il server — questo processo descrive la sequenza tecnica, non chi esegue ogni singolo passo.

---

**In sintesi**: backend — Linux + Python 3.11 + Uvicorn (1 worker) + MySQL 8 + Redis 7 + Nginx/TLS + volumi disco persistenti, con uscita di rete verso PrestaShop, FatturaPA e i corrieri; frontend — build statica Angular 17 servita dallo stesso Nginx, con fallback su `index.html` per il routing e CORS/URL API allineati al dominio di produzione. Prometheus, Grafana e Docker sono supporto, non prerequisiti.
