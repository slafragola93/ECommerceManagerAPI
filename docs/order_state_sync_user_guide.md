# Guida Utente: Sincronizzazione Automatica Stati Ordini

## 📋 Panoramica

Il sistema di sincronizzazione automatica degli stati ordini permette di **mantenere allineati** gli stati degli ordini tra il gestionale ECommerceManagerAPI e la piattaforma e-commerce (es. PrestaShop).

### Come Funziona

Quando cambi lo stato di un ordine nel gestionale, il sistema può **automaticamente aggiornare lo stato** anche sulla piattaforma e-commerce, senza dover fare modifiche manuali.

---

## 🔄 Flusso di Sincronizzazione

```
┌─────────────────────────────────────────────────────────────┐
│  1. Cambi lo stato di un ordine nel gestionale              │
│     (es. da "In Preparazione" a "Spediti")                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  2. Il sistema verifica se esiste un mapping configurato    │
│     nella tabella "Trigger Stati Piattaforma"               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  3. Se trovato, sincronizza automaticamente con PrestaShop  │
│     (crea una nuova entry in order_histories)                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  4. Aggiorna il campo "Stato E-commerce" nell'ordine locale │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Configurazione Trigger

### Cosa sono i Trigger?

I **trigger** sono regole che definiscono quale stato PrestaShop deve essere impostato quando cambi uno stato locale.

### Tabella Platform State Triggers

Ogni trigger contiene:

| Campo | Descrizione | Esempio |
|-------|-------------|---------|
| **Tipo Evento** | Quando scatta il trigger | `order_status_changed` |
| **Store** | Quale negozio interessa | Store ID: 1 |
| **Tipo Stato** | Ordine o Spedizione | `order_state` |
| **Stato Locale** | Lo stato nel gestionale | ID: 3 - "Spediti" |
| **Stato Piattaforma** | Lo stato PrestaShop corrispondente | ID: 4 - "05 - Spedito" |
| **Attivo** | Se il trigger è abilitato | ✅ Sì |

### Esempio Pratico

**Configurazione:**
- Stato Locale: **3** ("Spediti")
- Stato PrestaShop: **4** ("05 - Spedito")

**Cosa succede:**
1. Cambi un ordine allo stato "Spediti" (ID: 3)
2. Il sistema trova il trigger
3. Aggiorna automaticamente PrestaShop allo stato "05 - Spedito" (ID: 4)

---

## 📊 Stati E-commerce Disponibili

Gli stati e-commerce vengono sincronizzati automaticamente da PrestaShop ogni ora. Puoi vedere gli stati disponibili nella tabella `ecommerce_order_states`.

### Come Verificare gli Stati Sincronizzati

Chiama l'endpoint di inizializzazione:

```
GET /api/v1/init
```

Nella risposta troverai:

```json
{
  "ecommerce_order_states": [
    {
      "id_platform_state": 1,
      "id_store": 1,
      "name": "Contanti alla consegna"
    },
    {
      "id_platform_state": 3,
      "id_store": 1,
      "name": "03 - Preparazione ordine in corso...."
    },
    {
      "id_platform_state": 4,
      "id_store": 1,
      "name": "05 - Spedito"
    }
  ]
}
```

---

## 🎯 Come Creare un Nuovo Trigger

### Metodo 1: Via Database

Inserisci un record nella tabella `platform_state_triggers`:

```sql
INSERT INTO platform_state_triggers 
  (event_type, id_store, state_type, id_state_local, id_state_platform, is_active)
VALUES 
  ('order_status_changed', 1, 'order_state', 3, 3, 1);
```

**Parametri:**
- `event_type`: Sempre `'order_status_changed'` per stati ordini
- `id_store`: ID dello store (es. 1)
- `state_type`: `'order_state'` per ordini, `'shipping_state'` per spedizioni
- `id_state_local`: ID dello stato nel gestionale locale
- `id_state_platform`: ID record in `ecommerce_order_states` (non l'ID PrestaShop!)
- `is_active`: `1` per attivo, `0` per disattivo

### Metodo 2: Via API (Futuro)

_Endpoint in sviluppo per gestire i trigger tramite API_

---

## 🔍 Verifica Funzionamento

### 1. Controlla i Log

Dopo aver cambiato lo stato di un ordine, verifica nei log:

```
[RUNTIME] emit_event chiamato per evento: type=order_status_changed
platform_state_sync_handler - INFO - Stato ordine 32 sincronizzato con successo
platform_state_sync_handler - INFO - Updated order 32.id_ecommerce_state to 3
```

### 2. Verifica su PrestaShop

1. Accedi al backoffice PrestaShop
2. Vai su **Ordini** → Seleziona l'ordine
3. Controlla la **Storia Stati** - dovresti vedere la nuova entry

### 3. Verifica nel Gestionale

Quando recuperi l'ordine tramite API:

```
GET /api/v1/orders/32
```

Dovresti vedere:

```json
{
  "id_order": 32,
  "id_order_state": 3,
  "ecommerce_order_state": {
    "id": 3,
    "state_name": "03 - Preparazione ordine in corso...."
  }
}
```

---

## ⏰ Sincronizzazione Periodica

Il sistema sincronizza automaticamente gli stati PrestaShop:

- **Frequenza**: Ogni ora
- **Azione**: Recupera tutti gli stati disponibili su PrestaShop
- **Scopo**: Mantiene aggiornata la lista `ecommerce_order_states`

Questo garantisce che i nuovi stati creati su PrestaShop siano disponibili nel gestionale.

---

## ❓ Domande Frequenti

### Il trigger non si attiva. Cosa faccio?

1. **Verifica che il trigger esista**: Controlla nella tabella `platform_state_triggers`
2. **Verifica che sia attivo**: `is_active = 1`
3. **Controlla i parametri**: `id_state_local` deve corrispondere allo stato che stai impostando
4. **Verifica lo store**: `id_store` deve corrispondere allo store dell'ordine
5. **Controlla i log**: Cerca messaggi come "Nessun trigger trovato"

### Posso disattivare un trigger senza eliminarlo?

Sì! Imposta `is_active = 0` nella tabella `platform_state_triggers`.

### Posso mappare più stati locali allo stesso stato PrestaShop?

Sì, puoi creare più trigger che puntano allo stesso `id_state_platform`.

### La sincronizzazione fallisce. Perché?

Verifica:
- L'ordine ha un `id_origin` (ID PrestaShop) valido
- Le credenziali API PrestaShop sono corrette
- Lo stato PrestaShop esiste davvero
- I log per dettagli tecnici sull'errore

---

## 📞 Supporto

Per problemi o domande:
1. Controlla i log dell'applicazione
2. Verifica la configurazione dei trigger
3. Contatta il team di sviluppo con i dettagli del problema

