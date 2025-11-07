# Strategia Sistema Eventi Business

## Indice

- [Introduzione](#introduzione)
- [Perché Decorator invece di Middleware](#perché-decorator-invece-di-middleware)
- [Architettura del Sistema](#architettura-del-sistema)
- [Eventi Ricchi vs Eventi Poveri](#eventi-ricchi-vs-eventi-poveri)
- [Come Funziona](#come-funziona)
- [Creazione di Nuovi Eventi](#creazione-di-nuovi-eventi)
- [Plugin ed Eventi](#plugin-ed-eventi)
- [Best Practices](#best-practices)
- [Esempi Pratici](#esempi-pratici)
- [Troubleshooting](#troubleshooting)

---

## Introduzione

Il sistema eventi di ECommerceManagerAPI permette di **estendere le funzionalità** dell'applicazione attraverso **plugin isolati** che reagiscono agli eventi business (creazione ordini, aggiornamento clienti, ecc.) senza modificare il codice core.

### Obiettivi Chiave

✅ **Eventi Ricchi**: I plugin ricevono tutti i dati necessari senza query aggiuntive  
✅ **Isolamento**: Gli errori nei plugin non bloccano l'applicazione  
✅ **Estensibilità**: Aggiungere funzionalità senza modificare il core  
✅ **Performance**: Zero overhead se nessun plugin è attivo  
✅ **Manutenibilità**: Codice pulito e seguendo principi SOLID  

---

## Perché Decorator invece di Middleware

### ❌ Problema del Middleware

Il middleware HTTP intercetta richieste/risposte ma ha accesso **limitato** ai dati:

```python
# Middleware può vedere solo:
- Path: /api/v1/customers/123
- Method: POST
- Response HTTP: {"id_customer": 123, "email": "..."}

# ❌ NON può vedere:
- Dati interni (old_state_id)
- Oggetti completi dal DB
- Contesto business (is_new, customer_type, ecc.)
```

**Conseguenza per i Plugin**:
```python
# Plugin riceve evento "povero"
event.data = {"id_customer": 123}  # Solo ID!

# Plugin deve fare query extra per ottenere dati
customer = db.query(Customer).get(123)  # ❌ Query extra!
email = customer.email
firstname = customer.firstname
# ... altre query per dati correlati
```

### ✅ Soluzione con Decorator

I decorator nei **service** hanno accesso completo ai dati business:

```python
# Decorator può accedere a:
- Oggetti completi dal DB
- Dati di contesto (is_new, old_value)
- Dati calcolati (totals, counts)
- Relazioni (customer.addresses)
```

**Vantaggi per i Plugin**:
```python
# Plugin riceve evento "ricco"
event.data = {
    "id_customer": 123,
    "email": "customer@example.com",
    "firstname": "Mario",
    "lastname": "Rossi",
    "company": "ACME Corp",
    "is_new": True,  # Contesto business
    "tenant": "default",
    "created_by": 1
}

# ✅ Plugin può agire immediatamente senza query!
await send_welcome_email(
    to=event.data["email"],
    firstname=event.data["firstname"]
)
```

### Confronto

| Aspetto | Middleware | Decorator |
|---------|-----------|-----------|
| **Dati disponibili** | Solo HTTP (path/response) | Accesso completo business |
| **Performance plugin** | Query extra necessarie | Zero query extra |
| **Flessibilità** | Limitata | Totale |
| **Isolamento logica** | HTTP layer | Business layer |
| **Raccomandato per** | Audit/logging HTTP | Eventi business plugin |

---

## Architettura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                    API Endpoint (Router)                     │
│  POST /api/v1/customers                                      │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│              CustomerService (Business Logic)                │
│  @emit_event_on_success(EventType.CUSTOMER_CREATED, ...)   │
│  async def create_customer(...) -> (Customer, bool)         │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ├─► Esegue logica business
                   ├─► Salva nel DB
                   ├─► Ritorna risultato
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│          Decorator estrae dati ricchi dal result             │
│  extract_customer_created_data(result, kwargs)              │
│  ↓ Dati completi: email, nome, cognome, is_new, tenant     │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                     EventBus.publish()                       │
│  Emette Event(type="customer_created", data={...ricchi})    │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ├─────────┬─────────┬──────────┐
                   ▼         ▼         ▼          ▼
              Plugin A   Plugin B   Plugin C   Plugin N
              Email      CRM Sync   Audit      Analytics
              Handler    Handler    Logger     Tracker
```

### Componenti Principali

1. **Service**: Contiene la logica business, decorato con `@emit_event_on_success`
2. **Extractor**: Funzione che estrae dati ricchi dal risultato del service
3. **EventBus**: Distribuisce l'evento a tutti i plugin registrati
4. **Plugin**: Reagisce all'evento eseguendo azioni (email, sync, log, ecc.)
5. **Circuit Breaker**: Isola errori dei plugin (dopo 5 errori, disabilita temporaneamente)

---

## Eventi Ricchi vs Eventi Poveri

### Evento Povero (da evitare)

```python
Event(
    event_type="customer_created",
    data={"id_customer": 123}  # Solo ID
)
```

**Problema**: Plugin deve fare query per ottenere dati.

### Evento Ricco (raccomandato)

```python
Event(
    event_type="customer_created",
    data={
        # IDs e riferimenti
        "id_customer": 123,
        "id_origin": 5678,
        
        # Dati completi
        "email": "customer@example.com",
        "firstname": "Mario",
        "lastname": "Rossi",
        "company": "ACME Corp",
        
        # Contesto business
        "is_new": True,
        "has_newsletter": False,
        "is_guest": False,
        
        # Metadata
        "tenant": "default",
        "created_by": 1,
        "date_add": "2024-01-15T10:30:00Z"
    }
)
```

**Vantaggi**: Plugin può agire immediatamente senza query extra.

### Cosa Includere negli Eventi

✅ **SEMPRE includere**:
- IDs primari (id_customer, id_order, ecc.)
- IDs di riferimento (id_origin, external_ids)
- Dati core dell'entità (nome, email, stato)
- Timestamp (created_at, updated_at)
- Tenant/contesto (per multi-tenancy)
- User info (created_by, updated_by)
- Flag di stato (is_new, is_active, ecc.)

✅ **INCLUDERE se rilevante**:
- Dati di relazione (customer_name per un ordine)
- Contatori/totali (total_amount, items_count)
- Dati calcolati utili (full_name, formatted_address)
- Snapshot di entità correlate (per eventi complessi)

❌ **EVITARE**:
- Dati binari (file, immagini)
- Liste molto lunghe (>100 items)
- Dati sensibili non necessari (password, token)
- Oggetti ciclici o non serializzabili

---

## Come Funziona

### 1. Decorare il Metodo Service

```python
# src/services/routers/customer_service.py

from src.events.decorators import emit_event_on_success
from src.events.core.event import EventType
from src.events.extractors import extract_customer_created_data

class CustomerService:
    @emit_event_on_success(
        event_type=EventType.CUSTOMER_CREATED,
        data_extractor=extract_customer_created_data,
        source="customer_service.create_customer"
    )
    async def create_customer(
        self, 
        customer_data: CustomerSchema,
        user: dict = None  # ← Importante per tenant/user_id
    ) -> Tuple[Customer, bool]:
        # ... logica business ...
        customer = self._customer_repository.create(customer)
        return (customer, True)
```

### 2. Creare l'Estrattore

```python
# src/events/extractors.py

def extract_customer_created_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati completi per evento CUSTOMER_CREATED.
    
    Args:
        result: Tupla (Customer, bool) dal service
        kwargs: Contiene 'user' per tenant
    
    Returns:
        Dictionary con dati completi del customer
    """
    try:
        if not result or not isinstance(result, tuple):
            return None
        
        customer, is_created = result
        
        return {
            "id_customer": customer.id_customer,
            "email": customer.email,
            "firstname": customer.firstname,
            "lastname": customer.lastname,
            "is_new": is_created,
            "tenant": kwargs.get('user', {}).get('tenant', 'default'),
            "created_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione dati: {e}")
        return None
```

### 3. Creare un Plugin che Usa l'Evento

```python
# src/events/plugins/welcome_email/plugin.py

from src.events.interfaces import BaseEventHandler, EventHandlerPlugin
from src.events.core.event import Event, EventType

class WelcomeEmailHandler(BaseEventHandler):
    """Handler che invia email di benvenuto ai nuovi clienti."""
    
    def can_handle(self, event: Event) -> bool:
        # Ascolta solo customer_created E solo nuovi (non esistenti)
        return (
            event.event_type == EventType.CUSTOMER_CREATED.value
            and event.data.get("is_new") == True
        )
    
    async def handle(self, event: Event) -> None:
        """Invia email di benvenuto."""
        # ✅ Tutti i dati sono disponibili nell'evento!
        email = event.data["email"]
        firstname = event.data["firstname"]
        company = event.data.get("company")
        
        # Invia email (esempio)
        await send_email(
            to=email,
            subject=f"Benvenuto {firstname}!",
            body=f"Grazie per esserti registrato {company or ''}..."
        )
        
        logger.info(f"Email di benvenuto inviata a {email}")

class WelcomeEmailPlugin(EventHandlerPlugin):
    def get_handlers(self):
        return [WelcomeEmailHandler()]

def get_plugin():
    return WelcomeEmailPlugin()
```

---

## Creazione di Nuovi Eventi

### Step 1: Definire EventType

Aggiungi in `src/events/core/event.py`:

```python
class EventType(str, Enum):
    # ... eventi esistenti ...
    
    # Nuovo evento
    SHIPMENT_CREATED = "shipment_created"
    SHIPMENT_UPDATED = "shipment_updated"
```

### Step 2: Creare Estrattore

Aggiungi in `src/events/extractors.py`:

```python
def extract_shipment_created_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Estrae dati per evento SHIPMENT_CREATED.
    
    Args:
        result: Shipment creato dal service
        kwargs: Contiene 'user' per contesto
    
    Returns:
        Dictionary con dati completi della spedizione
    """
    try:
        shipment = result
        if not shipment:
            return None
        
        return {
            "id_shipping": shipment.id_shipping,
            "tracking": shipment.tracking,
            "weight": float(shipment.weight or 0),
            "price_tax_incl": float(shipment.price_tax_incl or 0),
            "id_carrier_api": shipment.id_carrier_api,
            "tenant": kwargs.get('user', {}).get('tenant', 'default'),
            "created_by": kwargs.get('user', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Errore estrazione shipment: {e}")
        return None
```

### Step 3: Decorare il Service

```python
# src/services/routers/shipping_service.py

from src.events.decorators import emit_event_on_success
from src.events.core.event import EventType
from src.events.extractors import extract_shipment_created_data

class ShippingService:
    @emit_event_on_success(
        event_type=EventType.SHIPMENT_CREATED,
        data_extractor=extract_shipment_created_data,
        source="shipping_service.create_shipment"
    )
    async def create_shipment(self, shipment_data, user: dict = None):
        # ... logica ...
        shipment = self.repository.create(shipment_data)
        return shipment
```

### Step 4: Passare il Parametro `user` dal Router

```python
# src/routers/shipping.py

@router.post("/")
async def create_shipment(
    shipment_data: ShippingSchema,
    user: dict = Depends(get_current_user),  # ← Dependency
    shipping_service: ShippingService = Depends(get_service)
):
    # Passa user al service
    return await shipping_service.create_shipment(
        shipment_data, 
        user=user  # ← Importante!
    )
```

---

## Plugin ed Eventi

### Come i Plugin Ricevono Eventi

I plugin si registrano automaticamente al caricamento:

```python
# Il plugin definisce quali eventi gestire
class MyHandler(BaseEventHandler):
    def can_handle(self, event: Event) -> bool:
        # Filtra gli eventi che vuoi gestire
        return event.event_type == EventType.CUSTOMER_CREATED.value
    
    async def handle(self, event: Event) -> None:
        # Usa i dati ricchi dall'evento
        customer_email = event.data["email"]
        # ... azioni del plugin ...
```

### Isolamento dei Plugin

Il sistema garantisce isolamento **totale**:

1. **Circuit Breaker**: Dopo 5 errori consecutivi, il plugin viene disabilitato temporaneamente (5 minuti)
2. **Exception Handling**: Gli errori vengono loggati ma non propagati
3. **Async Gather**: I plugin vengono eseguiti in parallelo senza bloccarsi a vicenda
4. **Moduli Separati**: Ogni plugin viene caricato in un modulo Python isolato

```python
# In PluginManager._safe_execute_handler()

try:
    await handler(event)  # Esegue plugin
    self._plugin_failures[plugin_name] = 0  # Reset errori se successo
except Exception as e:
    self._plugin_failures[plugin_name] += 1  # Incrementa contatore
    logger.exception(f"Plugin '{plugin_name}' failed: {e}")
    
    # Se supera 5 errori, circuit breaker si apre
    if self._plugin_failures[plugin_name] >= 5:
        logger.error(f"Plugin '{plugin_name}' circuit breaker OPEN")
        # Plugin disabilitato per 5 minuti
```

### Esempio: Plugin che non può Bloccare l'App

```python
class BrokenPlugin(BaseEventHandler):
    async def handle(self, event: Event) -> None:
        # Questo plugin ha un bug!
        raise Exception("BOOM! Plugin rotto")
        
# Quando viene emesso un evento:
# 1. Plugin viene eseguito
# 2. Exception viene catturata
# 3. Errore viene loggato
# 4. Contatore errori incrementato
# 5. Altri plugin continuano normalmente
# 6. Dopo 5 errori, plugin disabilitato temporaneamente
# 7. L'applicazione CONTINUA A FUNZIONARE ✅
```

---

## Best Practices

### 1. Naming Convention per Estrattori

```python
# Pattern: extract_{entity}_{action}_data
extract_customer_created_data
extract_order_updated_data
extract_preventivo_deleted_data
extract_bulk_preventivo_converted_data
```

### 2. Gestione Errori negli Estrattori

```python
def extract_customer_created_data(*args, result=None, **kwargs):
    try:
        # ... estrazione dati ...
        return data
    except Exception as e:
        # ✅ Logga l'errore
        logger.error(f"Errore estrazione: {e}", exc_info=True)
        # ✅ Ritorna None (l'evento non verrà emesso)
        return None
```

### 3. Type Safety

```python
def extract_customer_created_data(*args, result=None, **kwargs) -> Optional[Dict[str, Any]]:
    #                                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    #                                                         Type hint esplicito
```

### 4. Documentazione Estrattori

Ogni estrattore deve avere:
- Docstring completa
- Descrizione degli Args
- Esempio del Dictionary ritornato
- Gestione errori con logging

### 5. Passare `user` nei Router

```python
# ✅ CORRETTO
@router.post("/")
async def create_entity(
    data: Schema,
    user: dict = Depends(get_current_user),
    service: Service = Depends(get_service)
):
    return await service.create_entity(data, user=user)  # ← Passa user!

# ❌ SBAGLIATO
async def create_entity(...):
    return await service.create_entity(data)  # ← user mancante!
    # Risultato: tenant="default", created_by=None
```

### 6. Eventi Bulk

Per operazioni bulk, emetti **un singolo evento** con array di risultati:

```python
def extract_bulk_preventivo_deleted_data(*args, result=None, **kwargs):
    return {
        "ids_requested": [1, 2, 3, 4, 5],
        "ids_successful": [1, 2, 4],
        "ids_failed": [3, 5],
        "total_successful": 3,
        "total_failed": 2,
        "tenant": "default",
        "deleted_by": 1
    }
```

---

## Esempi Pratici

### Esempio 1: Plugin Email Benvenuto

```python
# Plugin che invia email ai nuovi clienti
class WelcomeEmailHandler(BaseEventHandler):
    def can_handle(self, event: Event) -> bool:
        return (
            event.event_type == EventType.CUSTOMER_CREATED.value
            and event.data.get("is_new") == True  # Solo nuovi
        )
    
    async def handle(self, event: Event) -> None:
        # ✅ Dati disponibili senza query
        await send_welcome_email(
            to=event.data["email"],
            firstname=event.data["firstname"]
        )
```

### Esempio 2: Plugin Sincronizzazione CRM

```python
# Plugin che sincronizza con CRM esterno
class CRMSyncHandler(BaseEventHandler):
    def can_handle(self, event: Event) -> bool:
        return event.event_type in [
            EventType.CUSTOMER_CREATED.value,
            EventType.CUSTOMER_UPDATED.value
        ]
    
    async def handle(self, event: Event) -> None:
        # ✅ Dati completi disponibili
        await crm_api.upsert_contact({
            "email": event.data["email"],
            "first_name": event.data["firstname"],
            "last_name": event.data["lastname"],
            "company": event.data.get("company"),
            "external_id": event.data["id_customer"]
        })
```

### Esempio 3: Plugin Audit Logger

```python
# Plugin che logga tutti gli eventi in DB esterno
class AuditLoggerHandler(BaseEventHandler):
    def can_handle(self, event: Event) -> bool:
        # Ascolta tutti gli eventi business
        return event.event_type in [
            "customer_created", "customer_updated", "customer_deleted",
            "order_created", "order_updated", "preventivo_created",
            # ... tutti gli eventi business
        ]
    
    async def handle(self, event: Event) -> None:
        # Logga in database esterno
        await audit_db.insert({
            "event_type": event.event_type,
            "event_data": json.dumps(event.data),
            "tenant": event.data.get("tenant"),
            "user_id": event.data.get("created_by") or event.data.get("updated_by"),
            "timestamp": event.timestamp
        })
```

### Esempio 4: Plugin Validazione Ordini (AS400)

```python
# Plugin che valida ordini con web service esterno
class AS400ValidationHandler(BaseEventHandler):
    def can_handle(self, event: Event) -> bool:
        return (
            event.event_type == EventType.ORDER_STATUS_CHANGED.value
            and event.data.get("old_state_id") == 1
            and event.data.get("new_state_id") == 2
        )
    
    async def handle(self, event: Event) -> None:
        # ✅ Dati ordine disponibili
        id_order = event.data["order_id"]
        
        # Chiama web service AS400
        result = await as400_client.validate_order(id_order)
        
        if not result.is_valid:
            # Notifica errore (non blocca l'ordine!)
            logger.error(f"AS400 validation failed for order {id_order}")
```

---

## Troubleshooting

### Evento non viene emesso

**Cause comuni**:
1. Estrattore ritorna `None` (controlla log per errori)
2. Parametro `user` non passato dal router
3. Decorator non applicato al metodo giusto

**Debug**:
```python
# Aggiungi log nell'estrattore
logger.info(f"Extractor called: result={result}, kwargs={kwargs}")
```

### Plugin non riceve evento

**Cause comuni**:
1. `can_handle()` ritorna `False`
2. Plugin disabilitato in configurazione
3. Circuit breaker aperto (troppe eccezioni)

**Debug**:
```python
# Verifica status plugin
GET /api/v1/events/plugins

# Risposta mostra:
{
    "plugins": {
        "my_plugin": {
            "enabled": false,  # ← Plugin disabilitato!
            "handlers": ["MyHandler"],
            "config": {...}
        }
    }
}
```

### Plugin causa errori ripetuti

**Soluzione**: Il circuit breaker disabilita automaticamente il plugin dopo 5 errori.

**Recovery**:
1. Attendi 5 minuti (circuit breaker si chiude automaticamente)
2. Oppure riavvia l'applicazione
3. Oppure disabilita/abilita il plugin via API

```bash
# Disabilita plugin
POST /api/v1/events/plugins/my_plugin/disable

# Abilita plugin (dopo fix)
POST /api/v1/events/plugins/my_plugin/enable
```

### Dati mancanti nell'evento

**Causa**: Estrattore non include tutti i campi necessari.

**Soluzione**: Aggiorna l'estrattore:

```python
def extract_customer_created_data(*args, result=None, **kwargs):
    # ... estrazione esistente ...
    
    # ✅ Aggiungi campo mancante
    "phone": getattr(customer, 'phone', None),
```

---

## Pattern Avanzati

### Evento Condizionale

Emetti evento solo se condizione è vera:

```python
@emit_event_on_success(
    event_type=EventType.ORDER_STATUS_CHANGED,
    data_extractor=extract_order_status_data,
    condition=lambda *args, result=None, **kwargs: (
        result.get("old_state_id") != result.get("new_state_id")
    ),
    source="order_service.update_status"
)
async def update_status(...):
    # Evento emesso SOLO se stato cambia davvero
```

### Eventi con Snapshot di Relazioni

Per eventi complessi, includi snapshot di entità correlate:

```python
def extract_order_created_data(*args, result=None, **kwargs):
    order = result
    
    return {
        # Dati ordine
        "id_order": order.id_order,
        "total_paid": float(order.total_paid),
        
        # Snapshot customer (evita query al plugin)
        "customer": {
            "id_customer": order.customer.id_customer,
            "email": order.customer.email,
            "firstname": order.customer.firstname,
            "lastname": order.customer.lastname
        } if order.customer else None,
        
        # Sommario articoli (max 10 per performance)
        "items": [
            {
                "id_order_detail": item.id_order_detail,
                "product_name": item.product_name,
                "quantity": item.product_quantity,
                "price": float(item.product_price)
            }
            for item in order.order_details[:10]
        ]
    }
```

---

## Conclusioni

Il sistema eventi con decorator offre:

✅ **Eventi ricchi** con dati completi per plugin efficienti  
✅ **Isolamento totale** con circuit breaker e error handling  
✅ **Estensibilità** via plugin senza modificare il core  
✅ **Performance** senza overhead se nessun plugin attivo  
✅ **SOLID** con SRP per estrattori, OCP per nuovi eventi  

### File di Riferimento

- `src/events/core/event.py` - Definizione EventType
- `src/events/extractors.py` - Estrattori di dati ricchi
- `src/events/decorators.py` - Decorator @emit_event_on_success
- `src/events/plugin_manager.py` - Gestione plugin con circuit breaker
- `docs/GUIDA_PLUGIN_SISTEMA.md` - Guida creazione plugin
- `docs/EVENT_SYSTEM.md` - Architettura generale

---

## Esempi di Estrattori Esistenti

### Customer Created

```python
{
    "id_customer": 123,
    "id_origin": 5678,
    "email": "customer@example.com",
    "firstname": "Mario",
    "lastname": "Rossi",
    "company": "ACME Corp",
    "is_new": True,
    "has_newsletter": False,
    "is_guest": False,
    "tenant": "default",
    "created_by": 1
}
```

### Preventivo Converted

```python
{
    "id_order_document": 456,
    "id_order": 789,
    "tenant": "user_23",
    "converted_by": 23
}
```

### Bulk Preventivo Deleted

```python
{
    "ids_requested": [71, 72, 73, 74, 75],
    "ids_successful": [71, 72, 74],
    "ids_failed": [73, 75],
    "total_requested": 5,
    "total_successful": 3,
    "total_failed": 2,
    "tenant": "default",
    "deleted_by": 1
}
```

---

**Ultima revisione**: 2024-01-15  
**Versione sistema**: 2.0.0

