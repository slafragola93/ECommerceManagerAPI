# Guida Ultra Semplice: Sistema Plugin e Eventi

## 🎯 Cos'è questo sistema?

Il sistema plugin è un meccanismo che permette di **eseguire azioni automatiche** quando succede qualcosa nell'applicazione. Per esempio, quando cambia lo stato di un ordine, puoi inviare una email o fare un'azione personalizzata.

---

## 📐 Architettura in 3 Componenti

### 1. **Event (Evento)**
Un **evento** è un messaggio che dice "è successa questa cosa!".

```
Evento = {
  tipo: "order_status_changed",      // Tipo di evento
  dati: { order_id: 123, ... },      // Informazioni sull'evento
  timestamp: "2024-01-01 10:00:00",  // Quando è successo
  metadata: { ... }                   // Dati extra
}
```

**Tipi di eventi disponibili:**
- `order_status_changed`: quando cambia lo stato di un ordine

### 2. **EventBus (Bus degli Eventi)**
L'**EventBus** è come una **posta centrale**:
- Riceve gli eventi pubblicati dall'applicazione
- Li invia a tutti i plugin interessati
- Esegue i plugin **in parallelo** (più veloce!)
- Se un plugin fallisce, gli altri continuano a funzionare

```
Applicazione → EventBus → Plugin 1
                       → Plugin 2
                       → Plugin 3
```

### 3. **Plugin**
Un **plugin** è un **pezzo di codice che reagisce agli eventi**.

**Struttura di un plugin:**
```
mio_plugin/
  ├── plugin.py          ← File principale del plugin
  ├── handlers.py        ← Codice che gestisce gli eventi (opzionale)
  ├── requirements.txt   ← Dipendenze Python (opzionale)
  └── README.md          ← Documentazione (opzionale)
```

**Cosa fa un plugin:**
1. **Implementa** l'interfaccia `EventHandlerPlugin`
2. **Espone** uno o più **handler** (gestori di eventi)
3. **Risponde** agli eventi quando arrivano

---

## 🔄 Come Funziona il Flusso

```
1. Ordine cambia stato
   ↓
2. Applicazione crea Event("order_status_changed", dati...)
   ↓
3. EventBus riceve l'evento
   ↓
4. EventBus trova tutti i plugin abbonati a "order_status_changed"
   ↓
5. EventBus chiama TUTTI i plugin in parallelo
   ↓
6. Ogni plugin esegue la sua azione (email, log, notifica, ecc.)
```

---

## 📁 Dove Vanno i Plugin?

I plugin possono stare in **due tipi di directory**:

### Plugin Core (sviluppati con l'app)
```
src/events/plugins/
  ├── email_notification/    ← Plugin di esempio
  └── customs/              ← Plugin personalizzati
      └── hello_console/
```

### Plugin Installati (da marketplace o manualmente)
```
src/events/plugins/marketplace_plugins/
  └── mio_plugin_installato/
```

**Le directory sono configurate in:** `config/event_handlers.yaml`

---

## ⚙️ Configurazione (config/event_handlers.yaml)

```yaml
plugin_directories:
  - src/events/plugins              # Plugin core
  - src/events/plugins/customs       # Plugin personalizzati
  - src/events/plugins/marketplace_plugins  # Plugin installati

enabled_handlers: []                # Lista handler abilitati (vuoto = tutti abilitati)
disabled_handlers: []               # Lista handler disabilitati

routes:
  order_status_changed: {}          # Routing opzionale per stato → handler

plugins:
  mio_plugin:
    enabled: true                   # Configurazione specifica per plugin

marketplace:
  enabled: false                    # Marketplace remoto (opzionale)
  base_url: "https://..."
```

---

## 🛠️ Come Creare un Plugin Semplice

### Step 1: Crea la cartella
```bash
mkdir -p src/events/plugins/customs/mio_plugin
cd src/events/plugins/customs/mio_plugin
```

### Step 2: Crea `plugin.py`
```python
"""Mio plugin personalizzato."""

from src.events.interfaces import BaseEventHandler, EventHandlerPlugin
from src.events.core.event import Event

# Handler che gestisce l'evento
class MioHandler(BaseEventHandler):
    def __init__(self):
        super().__init__(name="mio_handler")
    
    def can_handle(self, event: Event) -> bool:
        return event.event_type == "order_status_changed"
    
    async def handle(self, event: Event) -> None:
        order_id = event.data.get("order_id")
        print(f"🎉 Ordine {order_id} ha cambiato stato!")

# Plugin che espone l'handler
class MioPlugin(EventHandlerPlugin):
    def __init__(self):
        super().__init__(name="mio_plugin")
        self._handlers = [MioHandler()]
    
    def get_handlers(self):
        return self._handlers
    
    def get_metadata(self):
        return {"version": "1.0.0", "descrizione": "Plugin di esempio"}

# Factory function (obbligatoria!)
def get_plugin() -> EventHandlerPlugin:
    return MioPlugin()
```

### Step 3: Riavvia l'applicazione
Il plugin verrà **automaticamente scoperto e caricato**.

---

## 🔌 Endpoint API Disponibili

### Gestione Plugin
- **`GET /api/v1/events/plugins`** - Lista tutti i plugin e il loro stato
- **`POST /api/v1/events/plugins/{nome}/enable`** - Abilita un plugin
- **`POST /api/v1/events/plugins/{nome}/disable`** - Disabilita un plugin
- **`DELETE /api/v1/events/plugins/{nome}/uninstall`** - **Disinstalla definitivamente** un plugin (elimina i file)

### Marketplace (se abilitato)
- **`GET /api/v1/plugins/marketplace`** - Lista plugin disponibili sul marketplace
- **`POST /api/v1/plugins/install`** - Installa un plugin dal marketplace
- **`DELETE /api/v1/plugins/uninstall/{nome}`** - Disinstalla un plugin

### Configurazione
- **`POST /api/v1/events/reload-config`** - Ricarica la configurazione senza riavviare

---

## 📝 Differenza tra Disabilitare e Disinstallare

### **Disabilitare** (`/disable`)
- ✅ Il plugin rimane installato
- ✅ I file restano sul disco
- ✅ Si può riabilitare dopo
- ✅ La configurazione viene aggiornata nel YAML

**Usa quando:** vuoi temporaneamente fermare un plugin senza rimuoverlo.

### **Disinstallare** (`/uninstall`)
- ❌ Il plugin viene **eliminato completamente**
- ❌ I file vengono **rimossi dal filesystem**
- ❌ Non si può più riabilitare (devi reinstallarlo)
- ✅ La configurazione viene aggiornata nel YAML

**Usa quando:** non ti serve più il plugin e vuoi liberare spazio.

---

## 🚀 Esempio Pratico: Plugin "Hello Console"

Questo plugin stampa "Ciao!" quando uno stato cambia a ID = 2.

**File:** `src/events/plugins/customs/hello_console/plugin.py`

```python
class HelloConsoleHandler(BaseEventHandler):
    def can_handle(self, event: Event) -> bool:
        # Solo se è order_status_changed E nuovo stato = 2
        if event.event_type != "order_status_changed":
            return False
        return event.data.get("new_state_id") == 2
    
    async def handle(self, event: Event) -> None:
        print("Ciao! 👋")

class HelloConsolePlugin(EventHandlerPlugin):
    def get_handlers(self):
        return [HelloConsoleHandler()]
```

**Come disabilitarlo:**
```bash
POST /api/v1/events/plugins/hello_console/disable
```

**Come disinstallarlo:**
```bash
DELETE /api/v1/events/plugins/hello_console/uninstall
```

---

## 💡 Best Practices

1. **Un plugin = una responsabilità**: ogni plugin fa una cosa ben precisa
2. **Usa il nome corretto**: il nome del plugin deve essere unico
3. **Gestisci gli errori**: usa try/except nel metodo `handle()`
4. **Non bloccare**: il metodo `handle()` deve essere veloce
5. **Logga le azioni**: usa il logger Python per debug

---

## 🔍 Debug e Troubleshooting

### Il plugin non viene caricato?
- ✅ Verifica che `plugin.py` esista nella cartella del plugin
- ✅ Verifica che `get_plugin()` restituisca un `EventHandlerPlugin`
- ✅ Controlla `config/event_handlers.yaml` che la directory sia in `plugin_directories`
- ✅ Controlla i log dell'applicazione per errori

### Il plugin non riceve eventi?
- ✅ Verifica che `can_handle()` restituisca `True` per l'evento
- ✅ Verifica che il plugin sia **abilitato** (`enabled: true` nel YAML)
- ✅ Controlla `/api/v1/events/plugins` per vedere lo stato

### L'evento non viene pubblicato?
- ✅ Verifica che l'applicazione stia emettendo eventi (es. `OrderRepository.update()`)
- ✅ Controlla i log per vedere se l'EventBus riceve eventi

---

## 📚 Struttura File di Riferimento

```
src/events/
  ├── core/
  │   ├── event.py           ← Definizione Event e EventType
  │   └── event_bus.py        ← EventBus (pubblica/abbona eventi)
  ├── interfaces/
  │   ├── base_event_handler.py    ← BaseEventHandler (da implementare)
  │   └── event_handler_plugin.py   ← EventHandlerPlugin (da implementare)
  ├── plugin_manager.py       ← Gestisce lifecycle plugin
  ├── plugin_loader.py        ← Carica i plugin dal filesystem
  └── plugins/                ← Directory plugin
      ├── email_notification/ ← Esempio plugin
      └── customs/            ← I tuoi plugin qui!
```

---

## ✅ Riepilogo Quick Start

1. **Crea plugin** → Crea cartella + `plugin.py` con `get_plugin()`
2. **Riavvia app** → Il plugin viene automaticamente caricato
3. **Gestisci eventi** → Implementa `handle()` nel tuo handler
4. **Testa** → Cambia lo stato di un ordine e verifica che funzioni
5. **Gestisci** → Usa `/enable`, `/disable`, `/uninstall` per controllare i plugin

**Fine! 🎉**

