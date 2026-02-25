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


## 🏃‍♂️ Avvio Rapido

```bash
# 1. Setup iniziale (solo al primo accesso)
python scripts/setup_initial.py

# 2. Avvia il server
uvicorn src.main:app --reload

```

