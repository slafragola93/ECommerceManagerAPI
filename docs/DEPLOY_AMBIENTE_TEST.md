# Deploy ambiente di test — Elettronew API

Runbook Linux (venv + systemd + MySQL 8 + Redis 7) per il backend FastAPI.
Codice di riferimento: `origin/master` (include `9fca087`, sync POOL senza dump su disco).

Sostituisci i placeholder:

| Placeholder | Esempio |
|---|---|
| `APP_DIR` | `/opt/elettronew/api` |
| `APP_USER` | `elettronew` |
| `REPO_URL` | URL git del backend |
| `DB_NAME` / `DB_USER` / `DB_PASS` | credenziali MySQL **di test** |
| `DUMP_FILE` | `/tmp/elettronew_src.sql` |
| `FE_ORIGIN` | `https://gestionale-test.example.com` (origin del frontend, con schema) |
| `PUBLIC_HOST` | hostname pubblico dell’API (se usi Nginx) |

---

## 0. Cosa serve e cosa non serve

**Stack obbligatorio**

- Linux + Python **3.11**
- Uvicorn su `src.main:app`, porta 8000, **1 solo worker**
- MySQL 8 `utf8mb4` / InnoDB (servizio esterno, non è nel `docker-compose`)
- Redis 7 (`CACHE_BACKEND=hybrid`)
- Dump MySQL **già popolato** (non un database vuoto)

**Consigliato**

- Nginx + TLS verso `127.0.0.1:8000`
- systemd per il riavvio automatico

**Non necessario**

- PostgreSQL, Celery, Gunicorn, S3, Node sul server API
- Prometheus / Grafana / Redis Commander (solo osservabilità)
- Cartella `fatture_download/` (dal 2026-09-21 l’XML sta in DB)

**Non fare**

- `alembic upgrade head` su DB vuoto (29 tabelle core non le crea Alembic) — per un DB vuoto usa la procedura in §4a
- `python scripts/setup_initial.py` o `scripts/init_auth_data.py` sul dump (rischio utente `admin`/`admin`)
- `SEED_EU_VAT_TAXES=1`
- `--workers 4` come in `run_prod.ps1` (duplica job POOL/SDI/tracking e spezza l’SSE)
- Lasciare `FATTURAPA_SDI_API_SEND_ENABLED=true` se l’API key FatturaPA è quella di produzione
- Esporre 3306, 6379, 8000 in pubblico

Healthcheck reale: `GET /api/v1/monitoring/health`.
`GET /health` **non esiste** (è un errore nel Dockerfile).

La key FatturaPA usata dal sync è `app_configurations` (`category=fatturapa`, `name=api_key`), non `FATTURAPA_API_KEY` nel `.env`.

---

## 1. Prerequisiti host (una tantum)

```bash
sudo apt-get update
sudo apt-get install -y \
  git curl nginx \
  python3.11 python3.11-venv python3.11-dev \
  build-essential pkg-config \
  libffi-dev libssl-dev libxml2-dev libxslt1-dev \
  mysql-server redis-server
```

Se Python 3.11 non è nei repo della distro, installalo dalla PPA `deadsnakes` o usa l’equivalente della tua distribuzione. Il `Dockerfile` è su `python:3.11-slim`.

```bash
sudo systemctl enable --now mysql
sudo systemctl enable --now redis-server
python3.11 --version
redis-cli ping
# atteso: PONG
```

Crea utente e directory:

```bash
sudo useradd --system --create-home --shell /bin/bash elettronew
sudo mkdir -p /opt/elettronew/api /var/log/elettronew
sudo chown -R elettronew:elettronew /opt/elettronew /var/log/elettronew
```

Firewall: esporre solo 80/443 (e SSH). Non pubblicare 3306/6379/8000.

---

## 2. Codice

```bash
sudo -u elettronew -i
export APP_DIR=/opt/elettronew/api
git clone <REPO_URL> "$APP_DIR"
cd "$APP_DIR"
git checkout master
git pull origin master
git log -1 --oneline
# deve includere 9fca087 o un commit successivo
```

```bash
cd /opt/elettronew/api
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
mkdir -p logs media/uploads media/logos
cp env.example .env
chmod 600 .env
```

---

## 3. File `.env` di test

Modifica `/opt/elettronew/api/.env`. Valori minimi (da `src/database.py` e `env.example`):

```dotenv
DATABASE_MAIN_ADDRESS=127.0.0.1
DATABASE_MAIN_PORT=3306
DATABASE_MAIN_NAME=elettronew_test
DATABASE_MAIN_USER=elettronew_test
DATABASE_MAIN_PASSWORD=cambia_questa_password

SECRET_KEY=genera_una_chiave_nuova_non_quella_di_prod
CACHE_KEY_SALT=sale_cache_diverso_da_prod

ENVIRONMENT=test
DEBUG=false

CACHE_ENABLED=true
CACHE_BACKEND=hybrid
REDIS_URL=redis://127.0.0.1:6379/0

# Se Redis ha requirepass:
# REDIS_URL=redis://:LA_PASSWORD@127.0.0.1:6379/0

# Stessa API key FatturaPA di produzione? Tieni questi a false.
FATTURAPA_SDI_API_SEND_ENABLED=false
FATTURAPA_POOL_SYNC_ENABLED=false
FATTURAPA_SDI_EVENTS_SYNC_ENABLED=false
TRACKING_POLLING_ENABLED=false

# Non decommentare:
# SEED_EU_VAT_TAXES=1

PRESTASHOP_SSL_VERIFY=true
# Solo se il certificato PrestaShop di test è invalido:
# PRESTASHOP_SSL_VERIFY=false
```

Note:

- Se `DB_PASS` contiene `@`, `#`, `/` o `:`, va **URL-encoded** (es. `@` → `%40`). Alembic e SQLAlchemy usano la stessa stringa.
- `SECRET_KEY` e `CACHE_KEY_SALT` devono essere **nuovi**, non copiati da prod/dev.
- `FATTURAPA_API_KEY` in `.env` **non** è letta dal sync POOL. Se nel dump c’è la key di produzione, i flag sopra evitano invii e polling.
- PrestaShop / FastLDV: compila solo se li testi (`PRESTASHOP_*`, `FASTLDV_API_KEY`).

Genera `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 4. MySQL — dump già popolato + migration

Sul server di **origine** (dev/prod da cui copi i dati):

```bash
mysqldump -u SRC_USER -p --single-transaction --routines --triggers SRC_DB > elettronew_src.sql
```

Sul server di **test**:

```bash
sudo mysql <<'SQL'
CREATE DATABASE IF NOT EXISTS elettronew_test
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'elettronew_test'@'localhost' IDENTIFIED BY 'cambia_questa_password';
GRANT ALL PRIVILEGES ON elettronew_test.* TO 'elettronew_test'@'localhost';
FLUSH PRIVILEGES;
SQL

sudo mysql elettronew_test < /tmp/elettronew_src.sql
```

Poi, **con il venv attivo e il `.env` già compilato**:

```bash
cd /opt/elettronew/api
source venv/bin/activate
export PYTHONPATH=/opt/elettronew/api
alembic upgrade head
alembic current
```

`alembic current` deve mostrare una revision, non un errore `Can't locate revision`.

Non lanciare `scripts/setup_initial.py` su questo dump. Gli utenti, `app_configurations` e le aliquote arrivano dal dump.

MySQL deve ascoltare solo in rete privata / localhost.

---

### 4a. Bootstrap su database vuoto (nuovo ambiente, senza dump)

Questa sottosezione vale solo se l'ambiente **non** parte da un dump popolato (§4), ad esempio un primo deploy su un server nuovo o un ambiente azzerato da zero.

In questo caso `alembic upgrade head` fallisce (vedi §0, "Non fare"): la catena di migration non è ripercorribile da zero, perché diverse migration intermedie modificano tabelle core (es. `shipments`) che storicamente sono state create solo da `Base.metadata.create_all()`, mai da una migration Alembic vera e propria. La migration di baseline che le crea (`62e4b40e09f9`) è in fondo alla catena, non all'inizio, quindi su un DB vuoto arriva troppo tardi.

**Procedura verificata (locale, 2026-09-24)** per bootstrappare un DB vuoto in modo equivalente allo schema attuale:

1. Crea il database vuoto e l'utente (stessi comandi di §4, ma **senza** importare nessun dump).

2. Con venv attivo e `.env` già compilato, puntato al DB vuoto:

   ```bash
   cd /opt/elettronew/api
   source venv/bin/activate
   export PYTHONPATH=/opt/elettronew/api
   python -c "from src.database import Base, engine; Base.metadata.create_all(bind=engine)"
   ```

   Crea tutte le tabelle dei modelli nella forma attuale — lo stesso meccanismo già usato da `startup_event()` in `src/main.py`.

   **Non avviare l'app intera per farlo eseguire.** L'avvio completo (`lifespan`) fa partire anche i background task — tracking, sync POOL FatturaPA, eventi SDI, sync stati ordine — che possono chiamare servizi esterni reali anche con DB vuoto. Il comando sopra esegue solo `create_all`, isolato, senza toccare `lifespan`.

3. Allinea Alembic senza eseguire nessuna migration:

   ```bash
   alembic stamp head
   alembic current
   # atteso: 62e4b40e09f9 (head) — o la revision head corrente al momento del deploy
   ```

   `stamp` scrive solo la revision in `alembic_version`, non esegue DDL.

4. Solo a questo punto avvia l'app normalmente (systemd, §7), così i background task partono con lo schema già pronto.

**Verifica di coerenza (consigliata)**: se hai un altro database di riferimento con schema aggiornato, confronta l'elenco tabelle dei due schemi via `information_schema.TABLES` — devono coincidere a meno di `alembic_version` (assente prima dello `stamp`).

**Nota per il backlog**: la causa di fondo — catena di migration non ripercorribile da zero — andrebbe risolta con una consolidazione (squash) delle migration da `5c44d2400e1d` a `62e4b40e09f9` in un'unica migration coerente con lo schema attuale dei modelli. Non blocca questo deploy (si usa `create_all` + `stamp`), ma va pianificata separatamente: finché non si fa, ogni nuovo ambiente da zero richiede questa procedura invece del normale `alembic upgrade head`.

---

## 5. Redis

```bash
sudo systemctl enable --now redis-server
redis-cli ping
```

Default del runbook: nessun `requirepass`, bind su `127.0.0.1`. Se attivi `requirepass`, aggiorna `REDIS_URL` nel `.env`.

---

## 6. CORS (obbligatorio se c’è un frontend)

In `src/main.py` la whitelist è hardcoded:

```python
allow_origins=[
    "http://localhost:4200",
    "http://127.0.0.1:4200",
    "http://localhost:8082",
    "http://127.0.0.1:8082",
],
```

Aggiungi `FE_ORIGIN` (es. `https://gestionale-test.example.com`) e riavvia l’API. Senza questo il browser blocca login e tutte le chiamate.

Se FE e API sono su origini diverse, lo stesso origin serve anche per `GET /api/v1/events/stream` (SSE).

---

## 7. systemd — 1 worker

Crea `/etc/systemd/system/elettronew-api.service`:

```ini
[Unit]
Description=Elettronew API (test)
After=network.target mysql.service redis-server.service
Wants=mysql.service redis-server.service

[Service]
Type=simple
User=elettronew
Group=elettronew
WorkingDirectory=/opt/elettronew/api
Environment=PYTHONPATH=/opt/elettronew/api
EnvironmentFile=/opt/elettronew/api/.env
ExecStart=/opt/elettronew/api/venv/bin/uvicorn src.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`--workers 1` è vincolante: i job (stati ordine, tracking, POOL FatturaPA, eventi SDI) e l’SSE partono nel `lifespan` di ogni processo.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now elettronew-api
sudo systemctl status elettronew-api
sudo journalctl -u elettronew-api -f
```

All’avvio **non** deve comparire la cartella `fatture_download/` in `APP_DIR`.

---

## 8. Nginx (opzionale ma consigliato)

Esempio `/etc/nginx/sites-available/elettronew-api-test` — solo API, TLS già emesso con Certbot:

```nginx
server {
    listen 443 ssl http2;
    server_name PUBLIC_HOST;

    # ssl_certificate / ssl_certificate_key : gestiti da certbot

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
    }

    location /api/v1/events/stream {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
    }
}

server {
    listen 80;
    server_name PUBLIC_HOST;
    return 301 https://$host$request_uri;
}
```

```bash
sudo ln -s /etc/nginx/sites-available/elettronew-api-test /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Il frontend Angular è un deploy **separato**. Se lo servi dallo stesso Nginx: `try_files $uri $uri/ /index.html;` sulla root e l’API su `/api` o su un host dedicato. L’URL API nel FE non deve restare `localhost`.

Disco da backupare: `media/` e `logs/`. Non serve `fatture_download/`.

---

## 9. Smoke test

Sostituisci `BASE` (`http://127.0.0.1:8000` in locale sul server, oppure `https://PUBLIC_HOST`).

```bash
# Health (questo è l'endpoint giusto)
curl -sS "$BASE/api/v1/monitoring/health"

# OpenAPI
curl -sS -o /dev/null -w "%{http_code}\n" "$BASE/docs"

# Login (OAuth2 form: username + password di un utente del dump)
curl -sS -X POST "$BASE/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=USER_DUMP&password=PASS_DUMP"
```

Con il token (`Authorization: Bearer ...`):

```bash
# Lista documenti: deve esserci lifecycle, non xml_content
curl -sS "$BASE/api/v1/fiscal_documents/" -H "Authorization: Bearer $TOKEN"

# XML on-demand (usa un id reale del dump)
curl -sS "$BASE/api/v1/fiscal_documents/ID/xml" -H "Authorization: Bearer $TOKEN"
```

Checklist:

1. Health `status` healthy/degraded/slow, non 404
2. Login 200 con access token
3. Lista fatture: `lifecycle` presente; assenti in root `fatturapa_status`, `mail_status`, `identificativo_sdi`, `xml_content`
4. `GET .../xml` restituisce l’XML
5. Nessuna cartella `fatture_download/` creata all’avvio
6. Se il FE è collegato: niente errore CORS in console
7. Con i flag di §3, un `POST .../send-to-sdi` con `send_to_sdi=true` deve rispondere **400** (invio SDI spento)

Il FE di test deve già leggere `lifecycle` e l’endpoint `/xml`. Se è fermo al contratto flat, le schermate fatture si rompono anche con l’API verde.

---

## 10. Deploy successivi

```bash
cd /opt/elettronew/api
git pull origin master
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart elettronew-api
curl -sS http://127.0.0.1:8000/api/v1/monitoring/health
```

Conferma le migration **prima** di `upgrade head` su un dump che condivide dati reali.

---

## Contratto FE (ripasso)

Dal 2026-09-15, lista e dettaglio fatture/NC:

- niente `xml_content` → `GET /api/v1/fiscal_documents/{id}/xml`
- niente `fatturapa_*` / `mail_*` / `identificativo_sdi` in root → `lifecycle.fatturapa` / `lifecycle.mail`
- restano in root `status` (workflow) e `sdi_status` (esito AdE)
- sulle fatture c’è `stato_storno`; i campi solo-NC non compaiono sulle invoice

Doc operativa FatturaPA: [`docs/FATTURAPA.md`](FATTURAPA.md).
