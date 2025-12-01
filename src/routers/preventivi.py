from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from sqlalchemy.orm import Session
from src.database import get_db
from src.services.routers.auth_service import get_current_user
from src.models.user import User
from src.services.routers.preventivo_service import PreventivoService
from src.schemas.preventivo_schema import (
    PreventivoCreateSchema,
    PreventivoUpdateSchema,
    PreventivoResponseSchema,
    PreventivoDetailResponseSchema,
    PreventivoListResponseSchema,
    PreventivoStatsSchema,
    ArticoloPreventivoSchema,
    ArticoloPreventivoUpdateSchema,
    BulkPreventivoDeleteRequestSchema,
    BulkPreventivoDeleteResponseSchema,
    BulkPreventivoConvertRequestSchema,
    BulkPreventivoConvertResponseSchema,
    BulkRemoveArticoliRequestSchema,
    BulkRemoveArticoliResponseSchema,
    BulkUpdateArticoliItem,
    BulkUpdateArticoliResponseSchema
)

router = APIRouter(prefix="/api/v1/preventivi", tags=["Preventivi"])

# Dependency per servizio preventivi
def get_preventivo_service(db: Session = Depends(get_db)) -> PreventivoService:
    return PreventivoService(db)

# Dependency per utente autenticato
user_dependency = Depends(get_current_user)
db_dependency = Depends(get_db)


@router.post("/", 
             response_model=PreventivoResponseSchema, 
             status_code=status.HTTP_201_CREATED,
             summary="Crea nuovo preventivo",
             description="Crea un preventivo con customer, indirizzi e articoli. Supporta entità esistenti (per ID) o nuova creazione inline.",
             response_description="Preventivo creato con successo. Restituisce il preventivo completo con calcoli automatici.")
async def create_preventivo(
    preventivo_data: PreventivoCreateSchema = Body(
        ...,

example={
            "esempio_completo": {
                "summary": "Esempio completo con tutti i campi disponibili (* = obbligatorio)",
                "description": "Mostra tutti i campi disponibili. I campi contrassegnati con * sono obbligatori, gli altri sono opzionali. Puoi usare id esistente O creare nuove entità inline con 'data'.",
                "value": {
                    # CUSTOMER* (obbligatorio - usa 'id' per esistente O 'data' per nuovo)
                    "customer": {
                        "data": {
                            "firstname": "Mario",              # * obbligatorio se nuovo customer
                            "lastname": "Rossi",               # * obbligatorio se nuovo customer
                            "email": "mario.rossi@example.com", # * obbligatorio se nuovo customer
                            "id_lang": 1,                      # * obbligatorio se nuovo customer
                            "id_origin": 12345,                # ID esterno opzionale (es. PrestaShop)
                            "company": "Rossi SRL"             # Opzionale
                        }
                        # Alternativa: {"id": 294488}  per usare customer esistente
                    },
                    
                    # ADDRESS DELIVERY* (obbligatorio - usa 'id' per esistente O 'data' per nuovo)
                    "address_delivery": {
                        "data": {
                            "firstname": "Mario",              # * obbligatorio se nuovo address
                            "lastname": "Rossi",               # * obbligatorio se nuovo address
                            "address1": "Via Roma 123",        # * obbligatorio se nuovo address
                            "city": "Milano",                  # * obbligatorio se nuovo address
                            "postcode": "20100",               # * obbligatorio se nuovo address
                            "state": "MI",                     # * obbligatorio se nuovo address
                            "phone": "0212345678",             # * obbligatorio se nuovo address
                            "id_country": 1,                   # ID nazione (1=Italia)
                            "id_customer": 0,                  # Auto-assegnato
                            "id_origin": 67890,                # ID esterno opzionale
                            "id_platform": 1,                  # 0=manuale, 1=PrestaShop
                            "company": "Rossi SRL",            # Nome azienda
                            "address2": "Interno 5",           # Secondo indirizzo
                            "mobile_phone": "3331234567",      # Cellulare
                            "vat": "IT12345678901",            # Partita IVA
                            "dni": "RSSMRA80A01F205X",         # Codice fiscale
                            "pec": "rossi@pec.it",             # Email PEC
                            "sdi": "ABCDE12",                  # Codice SDI
                            "ipa": "ABC123"                    # Codice IPA
                        }
                        # Alternativa: {"id": 470625}  per usare address esistente
                    },
                    
                    # ADDRESS INVOICE (opzionale - se omesso usa address_delivery)
                    "address_invoice": {
                        "data": {
                            "firstname": "Mario",              # * obbligatorio se nuovo address
                            "lastname": "Rossi",               # * obbligatorio se nuovo address
                            "address1": "Via Fatture 456",     # * obbligatorio se nuovo address
                            "city": "Roma",                    # * obbligatorio se nuovo address
                            "postcode": "00100",               # * obbligatorio se nuovo address
                            "state": "RM",                     # * obbligatorio se nuovo address
                            "phone": "0698765432",             # * obbligatorio se nuovo address
                            "id_country": 1,
                            "company": "Rossi SRL Sede Legale",
                            "address2": "Piano 3",
                            "mobile_phone": "3339876543",
                            "vat": "IT12345678901",
                            "dni": "RSSMRA80A01F205X",
                            "pec": "amministrazione@pec.it",
                            "sdi": "ABCDE12",
                            "ipa": "ABC123"
                        }
                        # Alternativa: {"id": 470626} per usare address esistente
                        # Se omesso: viene usato address_delivery anche per fatturazione
                    },
                    
                    # SECTIONAL (opzionale - sezionale contabile)
                    "sectional": {
                        "data": {
                            "name": "Preventivi 2025"          # Nome sezionale (deduplica automatica)
                        }
                        # Alternativa: {"id": 9}  per usare sezionale esistente
                    },
                    
                    # SHIPPING (opzionale - dati spedizione)
                    "shipping": {
                        "price_tax_excl": 10.00,               # * obbligatorio se shipping presente
                        "price_tax_incl": 12.20,               # * obbligatorio se shipping presente
                        "id_carrier_api": 1,                   # * obbligatorio se shipping presente
                        "id_tax": 1,                           # * obbligatorio se shipping presente (aliquota IVA)
                        "shipping_message": "Consegna express 24h"  # Messaggio spedizione (opzionale)
                    },
                    
                    # ID_PAYMENT (opzionale - metodo di pagamento)
                    "id_payment": 3,                           # ID metodo pagamento (es. bonifico, carta)
                    
                    # IS_INVOICE_REQUESTED (opzionale - richiesta fattura)
                    "is_invoice_requested": True,              # Se richiedere fattura (default: False)
                    
                    # NOTE (opzionale - note generali)
                    "note": "Preventivo per progetto speciale - sconto applicato per cliente fedele",
                    
                    # TOTAL_DISCOUNT (opzionale - sconto totale documento)
                    "total_discount": 50.00,                   # Sconto totale sul documento (oltre agli sconti articoli)
                    
                    
                    # ARTICOLI* (obbligatorio - almeno un articolo)
                    "articoli": [
                        # Articolo con prodotto esistente
                        {
                            "id_product": 123,                 # ID prodotto esistente (alternativa a campi custom)
                            "product_qty": 2,                  # Quantità (default: 1)
                            "id_tax": 9,                       # * SEMPRE obbligatorio - aliquota IVA
                            "reduction_percent": 10.0,         # Sconto percentuale su articolo
                            "reduction_amount": 0.0,           # Sconto importo fisso su articolo
                            "note": "Versione aggiornata"      # Note specifiche articolo
                        },
                        # Articolo personalizzato (senza id_product)
                        {
                            "product_name": "Servizio installazione",     # * obbligatorio se no id_product
                            "product_reference": "SERV-INST-2025",        # * obbligatorio se no id_product
                            "product_price": 150.00,                      # * obbligatorio se no id_product (anche 0.0)
                            "product_weight": 0.0,                        # Peso articolo
                            "product_qty": 1,                             # * obbligatorio se no id_product
                            "id_tax": 9,                                  # * SEMPRE obbligatorio
                            "reduction_percent": 0.0,                     # Sconto percentuale
                            "reduction_amount": 25.00,                    # Sconto fisso
                            "note": "Include configurazione base"         # Note articolo
                        }
                    ],
                    
                    # ORDER_PACKAGES (opzionale - dimensioni colli)
                    "order_packages": [
                        {
                            "height": 30.0,                    # Altezza pacco (cm)
                            "width": 40.0,                     # Larghezza pacco (cm)
                            "depth": 25.0,                     # Profondità pacco (cm)
                            "length": 50.0,                    # Lunghezza pacco (cm)
                            "weight": 5.5,                     # Peso pacco (kg)
                            "value": 500.00                    # Valore dichiarato pacco
                        },
                        {
                            "height": 15.0,
                            "width": 20.0,
                            "depth": 10.0,
                            "length": 25.0,
                            "weight": 2.0,
                            "value": 150.00
                        }
                    ]
                }
            }
        }
    ),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Crea un nuovo preventivo con customer, indirizzi e articoli.
    
    **Customer** (obbligatorio):
    - ID esistente: `{"id": 123}` → riutilizza customer
    - Nuovo: `{"data": {...}}` → crea customer inline
    
    **Indirizzi**:
    - Delivery (obbligatorio): ID o oggetto completo
    - Invoice (opzionale): se omesso, riusa delivery
    - Deduplicazione: indirizzi identici → un solo record
    
    **Articoli**:
    - Prodotto esistente: `{"id_product": 123, "product_qty": 2, "id_tax": 9}`
    - Prodotto custom: richiesti `product_name`, `product_reference`, `product_price`, `product_qty`, `id_tax`
    - Prezzi sempre SENZA IVA (calcolo automatico)
    - Sconti: `reduction_percent` (%) o `reduction_amount` (EUR)
    
    **Sectional** (opzionale):
    - ID: `{"id": 1}` → usa esistente
    - Nome: `{"data": {"name": "X"}}` → riutilizza se esiste, altrimenti crea
    
    **Shipping** (opzionale):
    - Richiesti: `price_tax_excl`, `price_tax_incl`, `id_carrier_api`, `id_tax`
    - Crea oggetto Shipping separato riutilizzabile
    - `weight` impostato automaticamente = peso totale articoli
    
    **Calcoli automatici**:
    - `document_number`: sequenziale
    - `total_price_with_tax`: somma articoli (con IVA) + shipping
    - `total_weight`: somma pesi articoli
    - IVA: calcolata per ogni articolo in base a `id_tax`
    
    **Esempi**: Vedi esempi JSON in Swagger per scenari specifici.
    """
    service = get_preventivo_service(db)
    print(preventivo_data)
    return service.create_preventivo(preventivo_data, user["id"])


@router.get("/", 
            response_model=PreventivoListResponseSchema,
            summary="Lista preventivi",
            description="Recupera lista preventivi con paginazione e ricerca opzionale.",
            response_description="Lista preventivi con metadati paginazione.")
async def get_preventivi(
    page: int = Query(1, ge=1, description="Numero pagina (min: 1)"),
    limit: int = Query(100, ge=1, le=1000, description="Elementi per pagina (max: 1000)"),
    search: Optional[str] = Query(None, description="Ricerca per document_number o note"),
    show_details: bool = Query(False, description="Include articoli per ogni preventivo (default: false)"),
    sectionals_ids: Optional[str] = Query(None, description="ID sezionali separati da virgole (es: 1,2,3)"),
    payments_ids: Optional[str] = Query(None, description="ID pagamenti separati da virgole (es: 1,2,3)"),
    date_from: Optional[str] = Query(None, description="Data inizio filtro (formato: YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Data fine filtro (formato: YYYY-MM-DD)"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Lista preventivi con paginazione e filtri.
    
    **Parametri**:
    - `page`: Numero pagina (default: 1)
    - `limit`: Elementi per pagina (default: 100, max: 1000)
    - `search`: Cerca in document_number o note (opzionale)
    - `show_details`: Se true, include articoli (default: false, più performante)
    - `sectionals_ids`: ID sezionali separati da virgole (es: 1,2,3)
    - `payments_ids`: ID pagamenti separati da virgole (es: 1,2,3)
    - `date_from`: Data inizio filtro (formato: YYYY-MM-DD)
    - `date_to`: Data fine filtro (formato: YYYY-MM-DD)
    
    **Risposta**: Lista preventivi con total, page, limit per paginazione e statistiche.
    
    **Statistiche (stats)**:
    Le statistiche vengono calcolate applicando gli stessi filtri della lista e includono:
    - `total_not_converted`: Numero preventivi non convertiti (id_order null o 0)
    - `total_converted`: Numero preventivi convertiti in ordine
    - `total_price_with_tax`: Valore totale con IVA (escluse spese di spedizione)
    - `total_price_net`: Valore totale senza IVA (escluse spese di spedizione)
    - `converted_total_price_with_tax`: Valore totale con IVA dei preventivi convertiti
    - `converted_total_price_net`: Valore totale senza IVA dei preventivi convertiti
    
    **Nota**: I totali dei prezzi escludono le spese di spedizione per mostrare solo il valore degli articoli.
    """
    service = get_preventivo_service(db)
    skip = (page - 1) * limit
    
    preventivi = await service.get_preventivi(
        skip, limit, search, show_details, 
        sectionals_ids=sectionals_ids,
        payments_ids=payments_ids,
        date_from=date_from,
        date_to=date_to,
        user=user
    )
    
    # Calcola statistiche con gli stessi filtri
    stats_data = service.get_preventivi_stats(
        search=search,
        sectionals_ids=sectionals_ids,
        payments_ids=payments_ids,
        date_from=date_from,
        date_to=date_to
    )
    stats = PreventivoStatsSchema(**stats_data)
    
    return PreventivoListResponseSchema(
        preventivi=preventivi,
        total=len(preventivi),
        page=page,
        limit=limit,
        stats=stats
    )


@router.get("/{id_order_document}", 
            response_model=PreventivoDetailResponseSchema,
            summary="Dettaglio preventivo",
            description="Recupera preventivo completo con indirizzi, articoli e totali.",
            response_description="Preventivo con tutti i dettagli inclusi.")
async def get_preventivo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo (id_order_document)"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Recupera preventivo per ID con dettagli completi.
    
    Include: customer, indirizzi (delivery/invoice), sectional, shipping, payment, articoli, totali.
    """
    service = get_preventivo_service(db)
    preventivo = await service.get_preventivo(id_order_document, user=user)
    
    if not preventivo:
        raise HTTPException(status_code=404, detail="Preventivo non trovato")
    
    return preventivo


@router.put("/{id_order_document}", 
            response_model=PreventivoDetailResponseSchema,
            summary="Aggiorna preventivo completo",
            description="Modifica preventivo con supporto creazione/aggiornamento entità nidificate. Usa id=null per creare, id=presente per aggiornare.",
            response_description="Preventivo aggiornato con successo.")
async def update_preventivo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    preventivo_data: PreventivoUpdateSchema = Body(..., examples={
        "crea_nuovo_customer": {
            "summary": "Crea nuovo customer per il preventivo",
            "value": {
                "customer": {
                    "id": None,
                    "firstname": "Giovanni",
                    "lastname": "Verdi",
                    "email": "giovanni.verdi@example.com",
                    "id_lang": 1
                }
            }
        },
        "aggiorna_customer_esistente": {
            "summary": "Aggiorna customer esistente (ID 100)",
            "value": {
                "customer": {
                    "id": 100,
                    "firstname": "Giovanni",
                    "lastname": "Rossi",
                    "email": "giovanni.rossi@example.com"
                }
            }
        },
        "smart_merge_articoli": {
            "summary": "Smart merge articoli (update + create + delete)",
            "value": {
                "articoli": [
                    {
                        "id_order_detail": 123,
                        "product_qty": 5,
                        "product_price": 120.00
                    },
                    {
                        "id_order_detail": 124,
                        "reduction_percent": 15.0
                    },
                    {
                        "id_order_detail": None,
                        "product_name": "Nuovo prodotto",
                        "product_reference": "NEW-001",
                        "product_price": 50.00,
                        "product_qty": 2,
                        "id_tax": 9
                    }
                ]
            }
        },
        "update_completo": {
            "summary": "Aggiornamento completo con tutte le entità",
            "value": {
                "customer": {
                    "id": None,
                    "firstname": "Maria",
                    "lastname": "Bianchi",
                    "email": "maria.bianchi@example.com",
                    "id_lang": 1
                },
                "address_delivery": {
                    "id": None,
                    "firstname": "Maria",
                    "lastname": "Bianchi",
                    "address1": "Via Roma 123",
                    "city": "Milano",
                    "postcode": "20100",
                    "state": "MI",
                    "phone": "0212345678",
                    "id_country": 1
                },
                "sectional": {
                    "id": None,
                    "name": "Preventivi 2025"
                },
                "shipping": {
                    "id": None,
                    "price_tax_excl": 10.00,
                    "price_tax_incl": 12.20,
                    "id_carrier_api": 1,
                    "id_tax": 1
                },
                "articoli": [
                    {
                        "id_order_detail": None,
                        "product_name": "Prodotto A",
                        "product_reference": "PROD-A",
                        "product_price": 100.00,
                        "product_qty": 2,
                        "id_tax": 9
                    }
                ],
                "note": "Preventivo completamente aggiornato",
                "total_discount": 20.00
            }
        },
        "aggiornamento_base": {
            "summary": "Aggiorna solo campi semplici",
            "value": {
                "note": "Preventivo aggiornato",
                "is_invoice_requested": True,
                "id_payment": 1
            }
        }
    }),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Aggiorna preventivo esistente con supporto completo per entità nidificate.
    
    **Struttura JSON unificata:**
    - Ogni entità ha `id` + campi nello stesso oggetto
    - `id` presente (non null) → aggiorna entità esistente
    - `id` null → crea nuova entità
    
    **Entità supportate:**
    - `customer`: ID o creazione nuovo customer
    - `address_delivery`: ID o creazione nuovo indirizzo consegna
    - `address_invoice`: ID o creazione nuovo indirizzo fatturazione
    - `sectional`: ID o creazione nuovo sezionale
    - `shipping`: ID o creazione nuova spedizione
    
    **Smart merge per liste:**
    - `articoli`: update esistenti (id_order_detail presente), create nuovi (id null), delete mancanti
    - `order_packages`: update esistenti (id_order_package presente), create nuovi (id null), delete mancanti
    
    **Validazioni:**
    - Preventivo non deve essere convertito in ordine
    - Tutti gli ID forniti devono esistere
    - Campi obbligatori per nuove entità devono essere forniti
    - `id_tax` obbligatorio per nuovi articoli
    
    **Ricalcolo automatico:**
    - Totali ricalcolati automaticamente dopo modifiche articoli
    - Peso totale aggiornato automaticamente
    
    **Campi NON modificabili** (calcolati/immutabili):
    - `id_order` (gestito automaticamente durante conversione)
    - `document_number`, `type_document`, `total_weight`, `total_price_with_tax`, `date_add`
    """
    service = get_preventivo_service(db)
    # Converti user in dict per il service (gestisce sia User object che dict)
    user_id = user.id if hasattr(user, "id") else user.get("id") if isinstance(user, dict) else None
    user_dict = {"id": user_id}
    preventivo = service.update_preventivo(id_order_document, preventivo_data, user_id, user=user_dict)
    
    if not preventivo:
        raise HTTPException(status_code=404, detail="Preventivo non trovato")
    
    return preventivo


@router.post("/{id_order_document}/articoli", 
             response_model=ArticoloPreventivoSchema,
             status_code=status.HTTP_201_CREATED,
             summary="Aggiungi articolo",
             description="Aggiunge un nuovo articolo al preventivo esistente.",
             response_description="Articolo aggiunto con successo.")
async def add_articolo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    articolo: ArticoloPreventivoSchema = Body(..., examples={
        "prodotto_esistente": {
            "summary": "Articolo da prodotto esistente",
            "value": {
                "id_product": 123,
                "product_qty": 2,
                "id_tax": 9,
                "reduction_percent": 10.0
            }
        },
        "prodotto_custom": {
            "summary": "Articolo personalizzato",
            "value": {
                "product_name": "Servizio consulenza",
                "product_reference": "CONS-2024",
                "product_price": 500.00,
                "product_weight": 0.0,
                "product_qty": 1,
                "id_tax": 9,
                "reduction_amount": 50.0
            }
        }
    }),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Aggiunge articolo a preventivo esistente.
    
    Supporta prodotto esistente (id_product) o articolo custom (product_name, product_reference, product_price).
    `id_tax` sempre obbligatorio. Prezzi senza IVA.
    """
    service = get_preventivo_service(db)
    result = service.add_articolo(id_order_document, articolo)
    
    if not result:
        raise HTTPException(status_code=404, detail="Preventivo non trovato")
    
    return result


@router.put("/articoli/{id_order_detail}", 
            response_model=ArticoloPreventivoSchema,
            summary="Aggiorna articolo",
            description="Modifica articolo esistente. Solo i campi forniti vengono aggiornati.",
            response_description="Articolo aggiornato con successo.")
async def update_articolo(
    id_order_detail: int = Path(..., gt=0, description="ID dell'articolo (id_order_detail)"),
    articolo_data: ArticoloPreventivoUpdateSchema = Body(..., examples={
        "modifica_quantita": {
            "summary": "Modifica quantità e sconto",
            "value": {
                "product_qty": 5,
                "reduction_percent": 20.0
            }
        },
        "aggiornamento_completo": {
            "summary": "Aggiornamento completo articolo",
            "value": {
                "product_name": "Nuovo nome prodotto",
                "product_reference": "NEW-REF",
                "product_price": 150.00,
                "product_weight": 2.0,
                "product_qty": 3,
                "id_tax": 10,
                "reduction_percent": 15.0,
                "rda": "RDA2024"
            }
        }
    }),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Aggiorna articolo esistente nel preventivo.
    
    **Campi modificabili**: product_name, product_reference, product_price, product_weight, 
    product_qty, id_tax, reduction_percent, reduction_amount, rda.
    
    Solo i campi forniti vengono aggiornati. Totali preventivo ricalcolati automaticamente.
    """
    service = get_preventivo_service(db)
    result = service.update_articolo(id_order_detail, articolo_data)
    
    if not result:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    
    return result


@router.delete("/articoli/{id_order_detail}", 
               status_code=status.HTTP_204_NO_CONTENT,
               summary="Rimuovi articolo",
               description="Elimina articolo dal preventivo. I totali vengono ricalcolati automaticamente.",
               response_description="Articolo rimosso con successo.")
async def remove_articolo(
    id_order_detail: int = Path(..., gt=0, description="ID dell'articolo (id_order_detail)"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Rimuove articolo dal preventivo.
    
    Eliminazione definitiva. Totali preventivo ricalcolati automaticamente dopo rimozione.
    """
    service = get_preventivo_service(db)
    success = service.remove_articolo(id_order_detail)
    
    if not success:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    
    return None


@router.delete("/{id_order_document}", 
               status_code=status.HTTP_204_NO_CONTENT,
               summary="Elimina preventivo",
               description="Elimina preventivo e tutti i suoi articoli. Operazione irreversibile.",
               response_description="Preventivo eliminato con successo.")
async def delete_preventivo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Elimina preventivo definitivamente.
    
    **Eliminati**: preventivo + tutti gli articoli associati.
    
    **NON eliminati** (riutilizzabili):
    - Customer, indirizzi (usati da altri preventivi/ordini)
    - Shipping (se presente, riutilizzabile)
    - Ordine (se preventivo già convertito, l'ordine rimane)
    """
    service = get_preventivo_service(db)
    success = service.delete_preventivo(id_order_document)
    
    if not success:
        raise HTTPException(status_code=404, detail="Preventivo non trovato")
    
    return None

@router.post("/{id_order_document}/duplicate", 
             response_model=PreventivoResponseSchema,
             status_code=status.HTTP_201_CREATED,
             summary="Duplica preventivo",
             description="Crea copia completa del preventivo con stesso customer, indirizzi, articoli e totali.",
             response_description="Preventivo duplicato con successo.")
async def duplicate_preventivo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo da duplicare"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Duplica preventivo esistente creando copia completa.
    
    **Copiati**:
    - Customer, indirizzi, sectional, shipping (riutilizzati, stessi ID)
    - Articoli (copiati identicamente: prodotti, prezzi, quantità, sconti, IVA)
    - Totali (stesso total_price_with_tax, total_weight)
    
    **Nuovo**:
    - `document_number`: nuovo sequenziale
    - `date_add`, `updated_at`: data corrente
    - `id_order`: null (non collegato)
    - `note`: "Copia di {numero_originale}" + note originali
    
    **Riutilizzati** (stessi ID): shipping, customer, indirizzi, sectional.
    **Copiati** (nuovi record): tutti gli articoli.
    """
    service = get_preventivo_service(db)
    result = service.duplicate_preventivo(id_order_document, user["id"])
    
    if not result:
        raise HTTPException(status_code=404, detail="Preventivo non trovato")
    
    return result


@router.post("/{id_order_document}/convert-to-order", 
             status_code=status.HTTP_200_OK,
             summary="Converti preventivo in ordine",
             description="Converte preventivo in ordine trasferendo customer, indirizzi, articoli e totali.",
             response_description="Ordine creato dal preventivo.")
async def convert_to_order(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo da convertire"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Converte preventivo in ordine.
    
    **Trasferiti all'ordine**:
    - Customer, indirizzi, sectional (stessi ID)
    - Articoli (copiati: prezzi, quantità, sconti, IVA)
    - Shipping (riutilizzato, stesso ID)
    - Totali (total_price_with_tax, total_weight)
    
    **Ordine creato**:
    - `id_order_state`: 1 (pending)
    - `id_platform`: 1 (default)
    - `reference`: "PRV{document_number}"
    - `is_payed`: false
    - `id_payment`: null
    
    **Validazioni**: Preventivo deve esistere e non essere già convertito.
    **Risultato**: Preventivo collegato all'ordine tramite `id_order`. Conversione una sola volta.
    """
    service = get_preventivo_service(db)
    result = service.convert_to_order(id_order_document, user["id"])
    
    if not result:
        raise HTTPException(status_code=404, detail="Preventivo non trovato")
    
    return result


@router.post("/bulk-delete",
             status_code=status.HTTP_200_OK,
             response_model=BulkPreventivoDeleteResponseSchema,
             summary="Eliminazione massiva preventivi",
             description="Elimina più preventivi in modo massivo. Restituisce risultati dettagliati con successi e fallimenti.",
             response_description="Risultato eliminazione massiva.")
async def bulk_delete_preventivi(
    request: BulkPreventivoDeleteRequestSchema = Body(..., examples={
        "eliminazione_semplice": {
            "summary": "Eliminazione di 5 preventivi",
            "description": "Esempio base di eliminazione massiva",
            "value": {
                "ids": [71, 72, 73, 74, 75]
            }
        },
        "eliminazione_singola": {
            "summary": "Eliminazione di un singolo preventivo",
            "description": "Anche un solo ID è valido",
            "value": {
                "ids": [71]
            }
        }
    }),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Elimina più preventivi in modo massivo.
    
    **Input**: Lista di ID preventivi da eliminare.
    
    **Output**: Risposta con:
    - `successful`: Lista di ID eliminati con successo
    - `failed`: Lista di errori con dettagli (NOT_FOUND, DELETE_ERROR)
    - `summary`: Riepilogo (total, successful_count, failed_count)
    
    **Comportamento**:
    - Ogni preventivo viene eliminato indipendentemente
    - Errori non bloccano l'eliminazione degli altri
    - Operazione irreversibile
    """
    service = get_preventivo_service(db)
    return service.bulk_delete_preventivi(request.ids)


@router.post("/bulk-convert-to-orders",
             status_code=status.HTTP_200_OK,
             response_model=BulkPreventivoConvertResponseSchema,
             summary="Conversione massiva preventivi in ordini",
             description="Converte più preventivi in ordini in modo massivo. Restituisce risultati dettagliati con successi e fallimenti.",
             response_description="Risultato conversione massiva.")
async def bulk_convert_to_orders(
    request: BulkPreventivoConvertRequestSchema = Body(..., examples={
        "conversione_semplice": {
            "summary": "Conversione di 5 preventivi",
            "description": "Esempio base di conversione massiva",
            "value": {
                "ids": [71, 72, 73, 74, 75]
            }
        },
        "conversione_singola": {
            "summary": "Conversione di un singolo preventivo",
            "description": "Anche un solo ID è valido",
            "value": {
                "ids": [71]
            }
        }
    }),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Converte più preventivi in ordini in modo massivo.
    
    **Input**: Lista di ID preventivi da convertire.
    
    **Output**: Risposta con:
    - `successful`: Lista di conversioni riuscite (id_order_document, id_order, document_number)
    - `failed`: Lista di errori con dettagli (NOT_FOUND, VALIDATION_ERROR, CONVERSION_ERROR)
    - `summary`: Riepilogo (total, successful_count, failed_count)
    
    **Validazioni richieste per ogni preventivo**:
    - `id_address_delivery` deve essere presente
    - `id_address_invoice` deve essere presente
    - `id_customer` deve essere presente
    - `id_shipping` deve essere presente
    
    **Comportamento**:
    - Ogni preventivo viene convertito indipendentemente
    - Errori non bloccano la conversione degli altri
    - Preventivi già convertiti vengono saltati
    """
    service = get_preventivo_service(db)
    return service.bulk_convert_to_orders(request.ids, user["id"])


@router.post("/bulk-remove-articoli",
             status_code=status.HTTP_200_OK,
             response_model=BulkRemoveArticoliResponseSchema,
             summary="Eliminazione massiva articoli",
             description="Elimina più articoli da preventivi in modo massivo. Restituisce risultati dettagliati con successi e fallimenti.",
             response_description="Risultato eliminazione massiva articoli.")
async def bulk_remove_articoli(
    request: BulkRemoveArticoliRequestSchema = Body(..., examples={
        "eliminazione_semplice": {
                "ids": [101, 102, 103]
            },
        "eliminazione_singola": {
                "ids": [101]
            }
    }),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Elimina più articoli da preventivi in modo massivo.
    
    **Parametri**:
    - `ids`: Lista di ID order_detail da eliminare
    
    **Comportamento**:
    - Ogni articolo viene eliminato indipendentemente usando `remove_articolo`
    - Errori non bloccano l'eliminazione degli altri articoli
    - La cache viene invalidata automaticamente per ogni articolo rimosso
    - Restituisce lista di successi, fallimenti e summary
    """
    service = get_preventivo_service(db)
    return service.bulk_remove_articoli(request.ids)


@router.post("/bulk-update-articoli",
             status_code=status.HTTP_200_OK,
             response_model=BulkUpdateArticoliResponseSchema,
             summary="Aggiornamento massivo articoli",
             description="Aggiorna più articoli di preventivi in modo massivo. Restituisce risultati dettagliati con successi e fallimenti.",
             response_description="Risultato aggiornamento massivo articoli.")
async def bulk_update_articoli(
    articoli: List[BulkUpdateArticoliItem] = Body(..., min_items=1, examples={
        "aggiornamento_semplice": {
            "summary": "Aggiornamento di 2 articoli",
            "description": "Esempio base di aggiornamento massivo articoli",
            "value": [
                {
                    "id_order_detail": 101,
                    "product_qty": 5,
                    "product_price": 25.50
                },
                {
                    "id_order_detail": 102,
                    "reduction_percent": 10.0
                }
            ]
        },
        "aggiornamento_singolo": {
            "summary": "Aggiornamento di un singolo articolo",
            "description": "Anche un solo articolo è valido",
            "value": [
                {
                    "id_order_detail": 101,
                    "product_qty": 3
                }
            ]
        }
    }),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Aggiorna più articoli di preventivi in modo massivo.
    
    **Parametri**:
    - Array di articoli da aggiornare, ognuno con `id_order_detail` e i campi da modificare
    
    **Comportamento**:
    - Ogni articolo viene aggiornato indipendentemente usando `update_articolo`
    - Errori non bloccano l'aggiornamento degli altri articoli
    - La cache viene invalidata automaticamente per ogni articolo aggiornato
    - Restituisce lista di successi, fallimenti e summary
    """
    service = get_preventivo_service(db)
    return service.bulk_update_articoli(articoli)


@router.get("/{id_order_document}/download-pdf",
            status_code=status.HTTP_200_OK,
            summary="Genera PDF Preventivo",
            description="Genera il PDF del preventivo specificato",
            response_description="File PDF del preventivo")
async def download_preventivo_pdf(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Genera il PDF del preventivo specificato
    
    Args:
        id_order_document: ID del preventivo
        user: Utente autenticato
        db: Sessione database
        
    Returns:
        Response: File PDF del preventivo
        
    Raises:
        HTTPException: Se il preventivo non esiste
    """
    service = get_preventivo_service(db)
    
    # Verifica che il preventivo esista
    preventivo = await service.get_preventivo(id_order_document)
    if not preventivo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preventivo non trovato"
        )
    
    # Genera il PDF
    try:
        pdf_content = await service.generate_preventivo_pdf(id_order_document)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore durante la generazione del PDF: {str(e)}"
        )
    
    # Restituisce il PDF come risposta
    from fastapi.responses import StreamingResponse
    from io import BytesIO
    
    # Crea un buffer per il PDF
    pdf_buffer = BytesIO(pdf_content)
    
    # Determina nome file
    filename = f"Preventivo-{preventivo.document_number}.pdf"
    
    # Ritorna PDF con headers per forzare download
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
            "Content-Type": "application/pdf"
        }
    )