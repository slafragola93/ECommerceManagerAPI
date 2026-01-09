# Eventi Attualmente Implementati

Questo documento elenca tutti gli eventi che sono attualmente **triggerabili** (implementati) nel sistema.

> **Nota**: Questo file viene generato manualmente. Se aggiungi nuovi eventi, aggiorna questo documento.

---

## 📋 Indice Eventi per Categoria

### 🛒 ORDINI
| Evento | Valore | Implementato in | Descrizione |
|--------|--------|-----------------|-------------|
| `ORDER_STATUS_CHANGED` | `order_status_changed` | `src/services/routers/order_service.py` | Emesso quando cambia lo stato di un ordine |
| `ORDER_CREATED` | `order_created` | `src/services/routers/order_service.py` | Emesso quando viene creato un nuovo ordine |

### 📦 SPEDIZIONI
| Evento | Valore | Implementato in | Descrizione |
|--------|--------|-----------------|-------------|
| `SHIPMENT_CREATED` | `shipment_created` | `src/routers/shipments.py` | Emesso quando viene creata una spedizione (singola o bulk) |
| `SHIPPING_STATUS_CHANGED` | `shipping_status_changed` | `src/services/routers/shipping_service.py` | Emesso quando cambia lo stato di una spedizione |

### 📄 DOCUMENTI
| Evento | Valore | Implementato in | Descrizione |
|--------|--------|-----------------|-------------|
| `DOCUMENT_CREATED` | `document_created` | `src/services/routers/preventivo_service.py`<br>`src/services/routers/ddt_service.py`<br>`src/services/routers/fiscal_document_service.py` | Emesso quando viene creato un documento (preventivo, DDT, fattura, nota di credito) |
| `DOCUMENT_UPDATED` | `document_updated` | `src/services/routers/preventivo_service.py`<br>`src/services/routers/ddt_service.py` | Emesso quando viene aggiornato un documento |
| `DOCUMENT_DELETED` | `document_deleted` | `src/services/routers/preventivo_service.py`<br>`src/services/routers/ddt_service.py` | Emesso quando viene eliminato un documento |
| `DOCUMENT_CONVERTED` | `document_converted` | `src/services/routers/preventivo_service.py` | Emesso quando un preventivo viene convertito in ordine |
| `DOCUMENT_BULK_DELETED` | `document_bulk_deleted` | `src/services/routers/preventivo_service.py` | Emesso quando vengono eliminate più documenti in bulk |

### 👤 CLIENTI
| Evento | Valore | Implementato in | Descrizione |
|--------|--------|-----------------|-------------|
| `CUSTOMER_CREATED` | `customer_created` | `src/services/routers/customer_service.py` | Emesso quando viene creato un nuovo cliente |
| `CUSTOMER_UPDATED` | `customer_updated` | `src/services/routers/customer_service.py` | Emesso quando viene aggiornato un cliente |
| `CUSTOMER_DELETED` | `customer_deleted` | `src/services/routers/customer_service.py` | Emesso quando viene eliminato un cliente |

### 🏷️ PRODOTTI
| Evento | Valore | Implementato in | Descrizione |
|--------|--------|-----------------|-------------|
| `PRODUCT_CREATED` | `product_created` | `src/services/routers/product_service.py` | Emesso quando viene creato un nuovo prodotto |
| `PRODUCT_UPDATED` | `product_updated` | `src/services/routers/product_service.py` | Emesso quando viene aggiornato un prodotto |

### 📍 INDIRIZZI
| Evento | Valore | Implementato in | Descrizione |
|--------|--------|-----------------|-------------|
| `ADDRESS_CREATED` | `address_created` | `src/services/routers/address_service.py` | Emesso quando viene creato un nuovo indirizzo |

---

## 📊 Riepilogo

**Totale eventi implementati: 15**

- **Ordini**: 2 eventi
- **Spedizioni**: 2 eventi
- **Documenti**: 5 eventi
- **Clienti**: 3 eventi
- **Prodotti**: 2 eventi
- **Indirizzi**: 1 evento

---

## 🔍 Come Verificare se un Evento è Implementato

Per verificare se un evento è implementato, cerca nel codebase:

1. **Decorator `@emit_event_on_success`** con il tipo di evento
2. **Chiamate dirette a `emit_event()`** con il tipo di evento

Esempio di ricerca:
```bash
# Cerca decorator
grep -r "@emit_event_on_success" --include="*.py" | grep "EventType.NOME_EVENTO"

# Cerca chiamate dirette
grep -r "emit_event" --include="*.py" | grep "EventType.NOME_EVENTO"
```

---

## 📝 Note

- Gli eventi sono definiti nell'enum `EventType` in `src/events/core/event.py`
- Gli eventi vengono emessi tramite il sistema di eventi centralizzato (`src/events/runtime.py`)
- I plugin possono sottoscriversi a questi eventi tramite il sistema di plugin (`src/events/plugin_manager.py`)
- Alcuni eventi possono essere emessi da più punti del codice (es. `DOCUMENT_CREATED` per diversi tipi di documenti)

---

**Ultimo aggiornamento**: 2024-12-19
