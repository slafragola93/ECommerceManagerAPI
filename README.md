# ECommerceManagerAPI

API che permette di gestire gli ordini su Prestashop.

## 🚀 Setup Iniziale

**⚠️ IMPORTANTE**: Prima del primo utilizzo, eseguire il setup iniziale:

```bash
# Setup automatico completo
python scripts/setup_initial.py

# Oppure setup manuale
python scripts/init_app_configurations.py
python scripts/init_order_states.py
python scripts/init_prestashop_platform.py
```

📖 **Documentazione completa**: [SETUP_INIZIALE.md](SETUP_INIZIALE.md)

## 🏃‍♂️ Avvio Rapido

```bash
# 1. Setup iniziale (solo al primo accesso)
python scripts/setup_initial.py

# 2. Avvia il server
uvicorn src.main:app --reload

# 3. Testa l'API
curl http://localhost:8000/api/v1/health
```

## 📚 Documentazione

- [Setup Iniziale](SETUP_INIZIALE.md) - Guida completa al setup
- [Sincronizzazione E-commerce](docs/ECOMMERCE_SYNC.md) - Documentazione sincronizzazione
