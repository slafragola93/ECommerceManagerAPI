# 🚀 Setup Iniziale ECommerceManagerAPI

## 📋 Checklist Setup Primo Accesso

### 1. **Configurazione App Configurations**
Prima di utilizzare l'API, è necessario configurare le impostazioni base:

```bash
# Eseguire lo script di inizializzazione
python scripts/init_app_configurations.py
```

**Configurazioni richieste:**
- ✅ Nome applicazione
- ✅ Versione API
- ✅ URL base
- ✅ Configurazioni database
- ✅ Impostazioni di sicurezza

### 2. **Inizializzazione Order States**
Creare gli stati degli ordini necessari per il funzionamento:

```sql
-- Query SQL per inserire order_states
INSERT INTO order_states (id_order_state, name) VALUES 
(1, 'In Preparazione'),
(2, 'Pronti Per La Spedizione'),
(3, 'Spediti'),
(4, 'Spedizione Confermata'),
(5, 'Annullati'),
(6, 'In Attesa');
```

**Oppure eseguire lo script Python:**
```bash
python scripts/init_order_states.py
```

### 3. **Configurazione Piattaforma E-commerce**
Configurare la connessione con PrestaShop:

```bash
# Eseguire lo script di configurazione PrestaShop
python scripts/init_prestashop_platform.py
```

**Configurazioni richieste:**
- ✅ URL API PrestaShop
- ✅ API Key PrestaShop
- ✅ Configurazioni di sincronizzazione

### 4. **Verifica Database**
Controllare che tutte le tabelle siano create correttamente:

```bash
# Eseguire le migrazioni Alembic
alembic upgrade head
```

### 5. **Test Connessione**
Verificare che tutto funzioni correttamente:

```bash
# Avviare il server
uvicorn src.main:app --reload

# Testare endpoint di salute
curl http://localhost:8000/api/v1/health
```

## 🔧 Script di Setup Automatico

### **Script Completo di Inizializzazione**
Creare uno script `setup_initial.py` che esegua automaticamente:

1. ✅ Controllo se è il primo accesso
2. ✅ Inizializzazione app_configurations
3. ✅ Creazione order_states
4. ✅ Configurazione piattaforma e-commerce
5. ✅ Verifica setup completato

### **Implementazione Suggerita**

```python
# scripts/setup_initial.py
def check_first_access():
    """Controlla se è il primo accesso al sistema"""
    # Verifica se app_configurations esiste
    # Verifica se order_states sono presenti
    # Verifica se piattaforma e-commerce è configurata

def setup_initial():
    """Esegue il setup iniziale completo"""
    if check_first_access():
        print("🎉 Benvenuto! Eseguendo setup iniziale...")
        
        # 1. App Configurations
        setup_app_configurations()
        
        # 2. Order States
        setup_order_states()
        
        # 3. Piattaforma E-commerce
        setup_ecommerce_platform()
        
        print("✅ Setup iniziale completato!")
    else:
        print("ℹ️  Sistema già configurato.")
```

## 📝 Note Importanti

### **Ordine di Esecuzione**
1. **Prima**: App Configurations
2. **Secondo**: Order States
3. **Terzo**: Piattaforma E-commerce
4. **Ultimo**: Test connessione

### **Controlli di Sicurezza**
- ✅ Verificare che non ci siano duplicati
- ✅ Controllare foreign key constraints
- ✅ Validare configurazioni inserite

### **Rollback in Caso di Errore**
- ✅ Backup database prima del setup
- ✅ Script di rollback per annullare modifiche
- ✅ Log dettagliati per debugging

## 🚨 Troubleshooting

### **Errori Comuni**
1. **Foreign Key Constraint Order States**: Verificare che order_states esistano
2. **Foreign Key Constraint Platform**: Verificare che platforms esistano e foreign key sia corretto
3. **Connection Error**: Controllare configurazioni database
4. **API Key Invalid**: Verificare credenziali PrestaShop

### **Comandi di Verifica**
```bash
# Verificare order_states
python -c "from src.database import get_db; from src.models.order_state import OrderState; db = next(get_db()); print(f'Order States: {db.query(OrderState).count()}')"

# Verificare app_configurations
python -c "from src.database import get_db; from src.models.app_configuration import AppConfiguration; db = next(get_db()); print(f'App Configs: {db.query(AppConfiguration).count()}')"

# Verificare piattaforme
python -c "from src.database import get_db; from src.models.platform import Platform; db = next(get_db()); print(f'Platforms: {db.query(Platform).count()}')"

# Verificare dati sincronizzati
python -c "from src.database import get_db; from src.models.order import Order; from src.models.product import Product; from src.models.customer import Customer; db = next(get_db()); print(f'Orders: {db.query(Order).count()}, Products: {db.query(Product).count()}, Customers: {db.query(Customer).count()}')"
```

## 💾 Salvataggio Dati in Database

### **Funzioni Upsert Implementate**
Tutte le funzioni di sincronizzazione ora salvano effettivamente i dati nel database:

- ✅ **Languages**: `_upsert_language()` - Salva lingue
- ✅ **Countries**: `_upsert_country()` - Salva paesi
- ✅ **Brands**: `_upsert_brand()` - Salva marchi
- ✅ **Categories**: `_upsert_category()` - Salva categorie
- ✅ **Carriers**: `_upsert_carrier()` - Salva corrieri
- ✅ **Products**: `_upsert_product()` - Salva prodotti
- ✅ **Customers**: `_upsert_customer()` - Salva clienti
- ✅ **Payments**: `_upsert_payment()` - Salva metodi di pagamento
- ✅ **Addresses**: `_upsert_address()` - Salva indirizzi
- ✅ **Orders**: `_upsert_order()` - Salva ordini
- ✅ **Order Details**: `_upsert_order_detail()` - Salva dettagli ordini

### **Debug e Monitoraggio**
Ogni funzione upsert fornisce debug dettagliato:
```
DEBUG: Successfully upserted product 12345
DEBUG: Successfully upserted order 67890
DEBUG: Successfully upserted order detail 67890_12345
```

### **Gestione Errori**
In caso di errore, le funzioni restituiscono informazioni dettagliate:
```
DEBUG: Error upserting product 12345: Foreign key constraint fails
```

## 📅 Prossimi Sviluppi

### **Miglioramenti Futuri**
- [ ] Setup wizard interattivo
- [ ] Configurazione automatica da file
- [ ] Validazione configurazioni
- [ ] Setup per altri e-commerce (Magento, WooCommerce)
- [ ] Dashboard di configurazione web
- [ ] Upsert intelligente (update se esiste, insert se nuovo)
- [ ] Batch processing per grandi volumi di dati

---

**📌 Ricorda**: Eseguire sempre il setup iniziale prima del primo utilizzo dell'API!
