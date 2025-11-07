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
            "con_id_esistenti": {
                "summary": "Preventivo base con entità esistenti",
                "description": "Formato ottimale quando customer e indirizzi esistono già. Passa solo gli ID per massime performance.",
                "value": {
                    "customer": {"id": 294488},
                    "address_delivery": {"id": 470625},
                    "address_invoice": {"id": 470626},
                    "note": "Preventivo per cliente esistente",
                    "articoli": [
                        {
                            "id_product": 123,
                            "product_qty": 3,
                            "id_tax": 9,
                            "reduction_percent": 10.0
                        }
                    ]
                }
            },
            "crea_nuovo_customer": {
                "summary": "Preventivo con nuovo customer e address",
                "description": "Crea customer e indirizzi inline durante la creazione del preventivo. Passa oggetti completi invece di ID.",
                "value": {
                    "customer": {
                        "data": {
                            "firstname": "Mario",
                            "lastname": "Rossi",
                            "email": "mario.rossi@example.com",
                            "company": "Rossi SRL",
                            "id_origin": 0
                        }
                    },
                    "address_delivery": {
                        "data": {
                            "id_customer": 0,
                            "id_country": 1,
                            "firstname": "Mario",
                            "lastname": "Rossi",
                            "address1": "Via Roma 123",
                            "city": "Milano",
                            "postcode": "20100",
                            "phone": "02123456",
                            "id_origin": 0
                        }
                    },
                    "note": "Preventivo per nuovo cliente",
                    "articoli": [
                        {
                            "product_name": "Prodotto personalizzato",
                            "product_reference": "CUSTOM-001",
                            "product_price": 120.50,
                            "product_weight": 1.5,
                            "product_qty": 3,
                            "id_tax": 9
                        }
                    ]
                }
            },
            "senza_address_invoice": {
                "summary": "Preventivo senza indirizzo fatturazione",
                "description": "Se address_invoice è omesso, viene automaticamente riutilizzato address_delivery per fatturazione.",
                "value": {
                    "customer": {"id": 294488},
                    "address_delivery": {"id": 470625},
                    "note": "Delivery = Invoice",
                    "articoli": [
                        {
                            "id_product": 123,
                            "product_qty": 2,
                            "id_tax": 9
                        }
                    ]
                }
            },
            "prodotto_personalizzato": {
                "summary": "Articolo personalizzato (senza id_product)",
                "description": "Crea articoli custom senza riferimento a prodotti esistenti. Richiesti: product_name, product_reference, product_price, product_qty, id_tax.",
                "value": {
                    "customer": {"id": 294488},
                    "address_delivery": {"id": 470625},
                    "note": "Preventivo con articolo custom",
                    "articoli": [
                        {
                            "product_name": "Servizio di consulenza",
                            "product_reference": "SERV-CONS-2024",
                            "product_price": 500.00,
                            "product_weight": 0.0,
                            "product_qty": 1,
                            "id_tax": 9,
                            "reduction_percent": 15.0
                        }
                    ]
                }
            },
            "mix_prodotti": {
                "summary": "Articoli misti (esistenti + custom)",
                "description": "Combina prodotti esistenti (id_product) e articoli personalizzati nello stesso preventivo.",
                "value": {
                    "customer": {"id": 294488},
                    "address_delivery": {"id": 470625},
                    "articoli": [
                        {
                            "id_product": 123,
                            "product_qty": 2,
                            "id_tax": 9
                        },
                        {
                            "product_name": "Installazione",
                            "product_reference": "INST-001",
                            "product_price": 100.00,
                            "product_qty": 1,
                            "id_tax": 9,
                            "reduction_amount": 20.0
                        }
                    ]
                }
            },
            "con_spedizione": {
                "summary": "Preventivo con costi spedizione",
                "description": "Include costi di spedizione. Crea oggetto Shipping separato riutilizzabile. Richiesti: price_tax_excl, price_tax_incl, id_carrier_api, id_tax.",
                "value": {
                    "customer": {"id": 294488},
                    "address_delivery": {"id": 470625},
                    "shipping": {
                        "price_tax_excl": 10.00,
                        "price_tax_incl": 12.20,
                        "id_carrier_api": 1,
                        "id_tax": 1,
                        "shipping_message": "Spedizione express"
                    },
                    "articoli": [
                        {
                            "id_product": 123,
                            "product_qty": 2,
                            "id_tax": 9
                        }
                    ]
                }
            },
            "con_sectional_esistente": {
                "summary": "Sezionale esistente (per ID)",
                "description": "Collega preventivo a sezionale esistente usando solo l'ID.",
                "value": {
                    "customer": {"id": 294488},
                    "address_delivery": {"id": 470625},
                    "sectional": {"id": 1},
                    "articoli": [
                        {
                            "id_product": 123,
                            "product_qty": 1,
                            "id_tax": 1
                        }
                    ]
                }
            },
            "con_sectional_nuovo": {
                "summary": "Sezionale per nome (auto-deduplica)",
                "description": "Se esiste sezionale con stesso nome, viene riutilizzato. Altrimenti viene creato nuovo. Deduplicazione automatica.",
                "value": {
                    "customer": {"id": 294488},
                    "address_delivery": {"id": 470625},
                    "sectional": {
                        "data": {
                            "name": "Preventivi 2025"
                        }
                    },
                    "articoli": [
                        {
                            "id_product": 123,
                            "product_qty": 1,
                            "id_tax": 1
                        }
                    ]
                }
            },
            "con_fattura": {
                "summary": "Preventivo con richiesta fattura",
                "description": "Imposta is_invoice_requested=true per indicare richiesta fatturazione. Valore viene trasferito all'ordine in conversione.",
                "value": {
                    "customer": {"id": 294488},
                    "address_delivery": {"id": 470625},
                    "is_invoice_requested": True,
                    "articoli": [
                        {
                            "id_product": 123,
                            "product_qty": 1,
                            "id_tax": 1
                        }
                    ]
                }
            },
            "stesso_indirizzo": {
                "summary": "Deduplicazione indirizzi identici",
                "description": "Se address_invoice e address_delivery sono identici, viene creato un solo indirizzo e riutilizzato per entrambi. Evita duplicati.",
                "value": {
                    "customer": {
                        "data": {
                            "firstname": "Mario",
                            "lastname": "Rossi",
                            "email": "mario@example.com",
                            "id_origin": 0
                        }
                    },
                    "address_delivery": {
                        "data": {
                            "firstname": "Mario",
                            "lastname": "Rossi",
                            "address1": "Via Roma 1",
                            "address2": "",
                            "city": "Milano",
                            "postcode": "20100",
                            "state": "MI",
                            "phone": "123456789",
                            "id_country": 1,
                            "id_origin": 0
                        }
                    },
                    "address_invoice": {
                        "data": {
                            "firstname": "Mario",
                            "lastname": "Rossi",
                            "address1": "Via Roma 1",
                            "address2": "",
                            "city": "Milano",
                            "postcode": "20100",
                            "state": "MI",
                            "phone": "123456789",
                            "id_country": 1,
                            "id_origin": 0
                        }
                    },
                    "articoli": [
                        {
                            "id_product": 123,
                            "product_qty": 1,
                            "id_tax": 1
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
    
    **Risposta**: Lista preventivi con total, page, limit per paginazione.
    """
    service = get_preventivo_service(db)
    skip = (page - 1) * limit
    
    preventivi = await service.get_preventivi(skip, limit, search, show_details, user=user)
    
    return PreventivoListResponseSchema(
        preventivi=preventivi,
        total=len(preventivi),
        page=page,
        limit=limit
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
            summary="Aggiorna preventivo",
            description="Modifica campi di un preventivo esistente. Solo i campi forniti vengono aggiornati.",
            response_description="Preventivo aggiornato con successo.")
async def update_preventivo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    preventivo_data: PreventivoUpdateSchema = Body(..., examples={
        "aggiornamento_base": {
            "summary": "Aggiorna informazioni base",
            "value": {
                "note": "Preventivo aggiornato",
                "is_invoice_requested": True,
                "id_payment": 1
            }
        },
        "cambio_indirizzi": {
            "summary": "Cambia indirizzi",
            "value": {
                "id_address_delivery": 456,
                "id_address_invoice": 457
            }
        },
        "aggiornamento_completo": {
            "summary": "Aggiornamento completo",
            "value": {
                "id_customer": 123,
                "id_address_delivery": 456,
                "id_address_invoice": 457,
                "id_sectional": 1,
                "id_shipping": 5,
                "id_payment": 2,
                "note": "Preventivo completamente aggiornato",
                "is_invoice_requested": True
            }
        }
    }),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Aggiorna preventivo esistente (campi opzionali).
    
    **Campi modificabili**:
    - `id_customer`, `id_tax`, `note` (max 200 char), `is_invoice_requested`
    - `id_address_delivery`, `id_address_invoice`
    - `id_order`, `id_sectional`, `id_shipping`, `id_payment`
    
    **Campi NON modificabili** (calcolati/immutabili):
    - `document_number`, `type_document`, `total_weight`, `total_price_with_tax`, `date_add`
    
    **Validazione**: Tutti gli ID devono esistere. Solo campi forniti vengono aggiornati.
    """
    service = get_preventivo_service(db)
    preventivo = service.update_preventivo(id_order_document, preventivo_data, user["id"])
    
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
    preventivo = service.get_preventivo(id_order_document)
    if not preventivo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preventivo non trovato"
        )
    
    # Genera il PDF
    try:
        pdf_content = service.generate_preventivo_pdf(id_order_document)
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