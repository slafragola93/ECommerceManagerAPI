# ECommerceManagerAPI

API REST per ordini, resi, documenti fiscali, spedizioni e sincronizzazione e-commerce (PrestaShop).

---

## Requisiti

- **Python 3.10+**
- **MySQL**
- (Opzionale) Redis per cache

---

## Installazione dipendenze

```bash
# Dalla root del progetto
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

# Installa le dipendenze
pip install -r requirements.txt
```

---

## Configurazione

Copia il file ambiente e imposta le variabili (database e JWT):

```bash
# Windows
copy env.example .env

# Linux / macOS
cp env.example .env
```

Modifica `.env` con almeno:

- `DATABASE_MAIN_USER`, `DATABASE_MAIN_PASSWORD`, `DATABASE_MAIN_ADDRESS`, `DATABASE_MAIN_PORT`, `DATABASE_MAIN_NAME`
- `SECRET_KEY` (per JWT)

Applica le migrazioni al database:

```bash
alembic upgrade head
```

---

## Esecuzione script

**Setup iniziale** (Order State, Shipping State, App Configuration, Platform, Store, Role, utente admin, CompanyFiscalInfo):

```bash
python scripts/setup_initial.py
```

Altri script utili:

```bash
# Solo configurazioni app
python scripts/init_app_configurations.py

# Warm cache (se usi cache)
python scripts/warm_cache.py
```

---

## Avvio applicazione

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

- **API**: http://localhost:8000  
- **Swagger**: http://localhost:8000/docs  
- **Health**: http://localhost:8000/api/v1/health (se esposto)

---

## Documentazione

- [DOCUMENTAZIONE.md](DOCUMENTAZIONE.md) – panoramica e architettura  
- [QUICK_START.md](QUICK_START.md) – avvio rapido e comandi  
- [docs/](docs/) – guide specifiche (eventi, plugin, sync, ecc.)
