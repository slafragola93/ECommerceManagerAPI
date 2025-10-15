from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from sqlalchemy.orm import Session
from src.database import get_db
from src.services.auth import get_current_user
from src.models.user import User
from src.services.preventivo_service import PreventivoService
from src.schemas.preventivo_schema import (
    PreventivoCreateSchema,
    PreventivoUpdateSchema,
    PreventivoResponseSchema,
    PreventivoListResponseSchema,
    ArticoloPreventivoSchema,
    ArticoloPreventivoUpdateSchema
)

router = APIRouter(prefix="/api/v1/preventivi", tags=["Preventivi"])

# Dependency per servizio preventivi
def get_preventivo_service(db: Session = Depends(get_db)) -> PreventivoService:
    return PreventivoService(db)

# Dependency per utente autenticato
user_dependency = Depends(get_current_user)
db_dependency = Depends(get_db)


@router.post("/", response_model=PreventivoResponseSchema, status_code=status.HTTP_201_CREATED,
             response_description="Preventivo creato con successo")
async def create_preventivo(
    preventivo_data: PreventivoCreateSchema = Body(
        ...,
        examples={
            "con_id_esistenti": {
                "summary": "Preventivo con customer e address esistenti (solo ID)",
                "description": "Usa questo formato quando customer e indirizzi esistono già nel database. Passa solo gli ID.",
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
                "summary": "Preventivo creando nuovo customer e address",
                "description": "Usa questo formato per creare un nuovo customer e i suoi indirizzi. Passa gli oggetti completi invece degli ID.",
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
                "summary": "Preventivo senza address_invoice (usa delivery come invoice)",
                "description": "Se non specifichi address_invoice, verrà usato automaticamente address_delivery come indirizzo di fatturazione.",
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
                "summary": "Preventivo con prodotto personalizzato (id_origin=0)",
                "description": "Puoi creare prodotti personalizzati al volo senza id_product. Specifica tutti i dettagli del prodotto.",
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
                "summary": "Preventivo misto (prodotti esistenti + personalizzati)",
                "description": "Puoi combinare prodotti esistenti (con id_product) e prodotti personalizzati nello stesso preventivo.",
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
                "summary": "Preventivo con spedizione inclusa",
                "description": "Include i costi di spedizione nel preventivo. La spedizione crea un oggetto Shipping separato.",
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
                "summary": "Preventivo con sezionale esistente (ID)",
                "description": "Usa un sezionale già esistente nel database passando solo l'ID.",
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
                "summary": "Preventivo con sezionale nuovo o riutilizzo per nome",
                "description": "Se esiste già un sezionale con lo stesso nome, viene riutilizzato. Altrimenti ne viene creato uno nuovo.",
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
                "description": "Esempio di preventivo che richiede fatturazione.",
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
                "summary": "Indirizzo fatturazione = consegna (deduplica automatica)",
                "description": "Se address_invoice è uguale a address_delivery, viene creato un solo indirizzo e riutilizzato per entrambi.",
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
    Crea un nuovo preventivo
    
    ## Parametri Principali
    
    ### Customer (OBBLIGATORIO)
    - **Con ID esistente**: `{"id": 123}` -> Usa customer già presente in database
    - **Crea nuovo**: `{"data": {"firstname": "Mario", "lastname": "Rossi", "email": "...", ...}}` -> Crea nuovo customer
    - Il campo `id_customer` negli indirizzi viene **sempre ignorato** e sostituito con l'ID generato/esistente
    
    ### Address Delivery (OBBLIGATORIO)
    - **Con ID esistente**: `{"id": 456}` -> Usa indirizzo già presente
    - **Crea nuovo**: `{"data": {"firstname": "...", "address1": "...", ...}}` -> Crea nuovo indirizzo
    - Viene automaticamente associato al customer
    
    ### Address Invoice (OPZIONALE)
    - **Non specificato**: Usa automaticamente `address_delivery` anche per fatturazione
    - **Con ID**: `{"id": 789}` -> Usa indirizzo esistente
    - **Crea nuovo**: `{"data": {...}}` -> Crea nuovo indirizzo
    - **Deduplica intelligente**: Se i dati sono identici a `address_delivery`, viene **riutilizzato lo stesso ID** (evita duplicati)
    
    ### Sectional (OPZIONALE)
    - **Con ID esistente**: `{"id": 1}` -> Usa sezionale esistente
    - **Con nome**: `{"data": {"name": "Preventivi 2025"}}` -> Comportamento intelligente:
      - Se esiste un sezionale con quel **nome** -> **riutilizza** (deduplica automatica)
      - Se NON esiste -> **crea** nuovo sezionale
    - Se omesso: `id_sectional` sarà `null`
    
    ### Shipping (OPZIONALE)
    - **Campi obbligatori**:
      - `price_tax_excl`: Prezzo senza IVA (es. 7.99)
      - `price_tax_incl`: Prezzo con IVA (es. 9.74)
      - `id_carrier_api`: ID del corriere
      - `id_tax`: ID aliquota IVA per la spedizione
           - **Campi opzionali**:
             - `shipping_message`: Note sulla spedizione
    - Crea un oggetto `Shipping` separato collegato tramite `id_shipping`
    - Il campo `weight` della spedizione viene impostato automaticamente uguale al peso totale dei prodotti
    - Quando converti in ordine, la spedizione viene **riutilizzata** (non duplicata)
    
    ### Is Invoice Requested (OPZIONALE)
    - **Default**: `false` se non specificato
    - **Valori**: `true` o `false`
    - **Funzione**: Indica se il preventivo richiede fatturazione
    - **Trasferimento**: Questo valore viene trasferito all'ordine durante la conversione
    
    ### Articoli (Lista)
    - **Prodotto esistente**: Specifica solo `id_product`, `product_qty`, `id_tax`
    - **Prodotto personalizzato**: Specifica `product_name`, `product_reference`, `product_price`, `product_qty`, `id_tax`
    - **id_tax**: Sempre obbligatorio per calcolare l'IVA
    - **Sconti**: Usa `reduction_percent` (%) O `reduction_amount` (EUR), non entrambi
    - **IMPORTANTE**: Prezzi devono essere **SEMPRE SENZA IVA** (l'IVA viene calcolata automaticamente)
    
    ---
    
    ## Calcolo Totali Automatico
    
    ### Formula
    ```
    total_price_with_tax = Somma(articoli con IVA) + shipping.price_tax_incl
    total_weight = Somma(peso articoli)
    ```
    
    **Nota**: Il campo `weight` della spedizione viene impostato automaticamente uguale al peso totale dei prodotti.
    
    ### Esempio Pratico
    - Articolo: 10,50 EUR (senza IVA) x 1 qty, IVA 22% -> **12,81 EUR**
    - Spedizione: 9,74 EUR (con IVA)
    - **Total_price = 12,81 + 9,74 = 22,55 EUR**
    
    ### Dettaglio Calcolo per Articolo
    1. **Prezzo base** = `product_price x product_qty`
    2. **Sconto** = prezzo_base x (reduction_percent / 100) o reduction_amount
    3. **Prezzo scontato** = prezzo_base - sconto
    4. **IVA** = prezzo_scontato x (tax_percentage / 100)
    5. **Prezzo finale** = prezzo_scontato + IVA
    
    ---
    
    ## Deduplicazione Automatica
    
    Il sistema evita duplicati in due modi:
    
    1. **Indirizzi identici**: Se `address_invoice` = `address_delivery` -> crea **1 solo indirizzo**
    2. **Sectional per nome**: Se esiste già `name = "X"` -> **riutilizza ID esistente**
    
    ---
    
    ## Campi Generati Automaticamente
    
    - `document_number`: Numero sequenziale (es. "000001")
    - `total_price_with_tax`: Totale con IVA inclusa
    - `total_weight`: Peso totale
    - `id_shipping`: ID dell'oggetto Shipping creato (se presente)
    - `id_sectional`: ID del sezionale (creato/riutilizzato se presente)
    - `date_add`: Data di creazione
    - `updated_at`: Data ultimo aggiornamento
    
    ---
    
    ## Esempi Disponibili
    
    Vedi gli esempi in Swagger per casi d'uso specifici:
    - `con_id_esistenti`: Usa entità esistenti (customer, address)
    - `crea_nuovo_customer`: Crea tutto da zero
    - `senza_address_invoice`: Usa delivery come invoice
    - `prodotto_personalizzato`: Articolo custom
    - `mix_prodotti`: Mix prodotti esistenti + personalizzati
    - `con_spedizione`: Include spedizione
    - `con_sectional_esistente`: Usa sezionale esistente
    - `con_sectional_nuovo`: Crea/riutilizza sezionale per nome
    - `con_fattura`: Richiesta fatturazione
    - `stesso_indirizzo`: Deduplica automatica indirizzi
    """
    try:
        service = get_preventivo_service(db)
        return service.create_preventivo(preventivo_data, user["id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.get("/", response_model=PreventivoListResponseSchema,
            response_description="Lista preventivi recuperata con successo")
async def get_preventivi(
    page: int = Query(1, ge=1, description="Numero pagina"),
    limit: int = Query(100, ge=1, le=1000, description="Elementi per pagina"),
    search: Optional[str] = Query(None, description="Ricerca per numero, riferimento o note"),
    show_details: bool = Query(False, description="Se true, include gli articoli correlati per ogni preventivo"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Recupera lista preventivi con filtri
    
    Parametri:
    - page: Numero della pagina (default: 1)
    - limit: Numero di elementi per pagina (default: 100, max: 1000)
    - search: Testo di ricerca per numero documento o note (opzionale)
    - show_details: Se true, include gli articoli correlati per ogni preventivo (default: false)
    
    Esempi di utilizzo:
    - GET /api/v1/preventivi/ - Lista base senza articoli (performance ottimale)
    - GET /api/v1/preventivi/?show_details=true - Lista con articoli inclusi
    - GET /api/v1/preventivi/?search=000001&show_details=true - Ricerca con articoli
    """
    try:
        service = get_preventivo_service(db)
        skip = (page - 1) * limit
        
        preventivi = service.get_preventivi(skip, limit, search, show_details)
        
        return PreventivoListResponseSchema(
            preventivi=preventivi,
            total=len(preventivi),
            page=page,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.get("/{id_order_document}", response_model=PreventivoResponseSchema,
            response_description="Preventivo recuperato con successo")
async def get_preventivo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """Recupera preventivo per ID"""
    try:
        service = get_preventivo_service(db)
        preventivo = service.get_preventivo(id_order_document)
        
        if not preventivo:
            raise HTTPException(status_code=404, detail="Preventivo non trovato")
        
        return preventivo
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.put("/{id_order_document}", response_model=PreventivoResponseSchema,
            response_description="Preventivo aggiornato con successo")
async def update_preventivo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    preventivo_data: PreventivoUpdateSchema = ...,
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Aggiorna un preventivo esistente
    
    ## Campi Modificabili
    
    Puoi aggiornare tutti i seguenti campi del preventivo:
    
    ### Informazioni Base
    - **id_customer**: ID del cliente (deve esistere)
    - **id_tax**: ID dell'aliquota IVA (deve esistere)
    - **note**: Note del preventivo (max 200 caratteri)
    - **is_invoice_requested**: Se richiedere fattura (true/false)
    
    ### Indirizzi
    - **id_address_delivery**: ID indirizzo di consegna (deve esistere)
    - **id_address_invoice**: ID indirizzo di fatturazione (deve esistere)
    
    ### Collegamenti
    - **id_order**: ID ordine collegato (se presente)
    - **id_sectional**: ID sezionale (deve esistere)
    - **id_shipping**: ID spedizione (deve esistere)
    
    ## Campi NON Modificabili
    
    I seguenti campi non possono essere modificati per garantire l'integrità dei dati:
    - **document_number**: Numero documento (generato automaticamente)
    - **type_document**: Tipo documento (sempre "preventivo")
    - **total_weight**: Peso totale (calcolato automaticamente)
    - **total_price_with_tax**: Totale con IVA (calcolato automaticamente)
    - **date_add**: Data di creazione (immutabile)
    
    ## Validazioni
    
    - Tutti gli ID specificati devono esistere nelle rispettive tabelle
    - I campi sono tutti opzionali (solo i campi forniti vengono aggiornati)
    - La validazione avviene prima dell'aggiornamento
    
    ## Esempio
    
    ```json
    {
        "id_customer": 123,
        "id_address_delivery": 456,
        "id_address_invoice": 457,
        "note": "Preventivo aggiornato",
        "is_invoice_requested": true
    }
    ```
    """
    try:
        service = get_preventivo_service(db)
        preventivo = service.update_preventivo(id_order_document, preventivo_data, user["id"])
        
        if not preventivo:
            raise HTTPException(status_code=404, detail="Preventivo non trovato")
        
        return preventivo
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.post("/{id_order_document}/articoli", response_model=ArticoloPreventivoSchema,
             status_code=status.HTTP_201_CREATED, response_description="Articolo aggiunto con successo")
async def add_articolo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    articolo: ArticoloPreventivoSchema = ...,
    user: User = user_dependency,
    db: Session = db_dependency
):
    """Aggiunge articolo a preventivo"""
    try:
        service = get_preventivo_service(db)
        result = service.add_articolo(id_order_document, articolo)
        
        if not result:
            raise HTTPException(status_code=404, detail="Preventivo non trovato")
        
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.put("/articoli/{id_order_detail}", response_model=ArticoloPreventivoSchema,
            response_description="Articolo aggiornato con successo")
async def update_articolo(
    id_order_detail: int = Path(..., gt=0, description="ID dell'articolo"),
    articolo_data: ArticoloPreventivoUpdateSchema = ...,
    user: User = user_dependency,
    db: Session = db_dependency
):
    """Aggiorna articolo in preventivo"""
    try:
        service = get_preventivo_service(db)
        result = service.update_articolo(id_order_detail, articolo_data)
        
        if not result:
            raise HTTPException(status_code=404, detail="Articolo non trovato")
        
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.delete("/articoli/{id_order_detail}", status_code=status.HTTP_204_NO_CONTENT,
               response_description="Articolo rimosso con successo")
async def remove_articolo(
    id_order_detail: int = Path(..., gt=0, description="ID dell'articolo"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """Rimuove articolo da preventivo"""
    try:
        service = get_preventivo_service(db)
        success = service.remove_articolo(id_order_detail)
        
        if not success:
            raise HTTPException(status_code=404, detail="Articolo non trovato")
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.delete("/{id_order_document}", status_code=status.HTTP_204_NO_CONTENT,
               response_description="Preventivo eliminato con successo")
async def delete_preventivo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Elimina un preventivo
    
    Elimina il preventivo e tutti i suoi articoli associati.
    
    ## Note:
    - L'eliminazione è **definitiva e non reversibile**
    - Vengono eliminati anche **tutti gli articoli** del preventivo
    - L'oggetto **Shipping** (se presente) NON viene eliminato - potrebbe essere usato da altri preventivi/ordini
    - Se il preventivo è già stato convertito in ordine, l'**ordine NON verrà eliminato**
    - Il customer e gli indirizzi NON vengono eliminati (possono essere usati da altri preventivi/ordini)
    """
    try:
        service = get_preventivo_service(db)
        success = service.delete_preventivo(id_order_document)
        
        if not success:
            raise HTTPException(status_code=404, detail="Preventivo non trovato")
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.post("/{id_order_document}/duplicate", response_model=PreventivoResponseSchema,
             status_code=status.HTTP_201_CREATED, response_description="Preventivo duplicato con successo")
async def duplicate_preventivo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo da duplicare"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Duplica un preventivo esistente
    
    Crea una copia completa del preventivo specificato con tutte le sue caratteristiche.
    
    ## Dati Copiati
    
    ### Informazioni Base
    - **Customer**: Stesso cliente del preventivo originale
    - **Indirizzi**: Stessi indirizzi di consegna e fatturazione
    - **Sectional**: Stesso sezionale (se presente)
    - **Shipping**: Stessa spedizione (riutilizzo oggetto esistente)
    - **Note**: Aggiunge prefisso "Copia di {numero_originale}" alle note esistenti
    
    ### Articoli
    - Tutti gli articoli vengono **copiati identicamente** mantenendo:
      - Stessi prodotti (id_product)
      - Stessi prezzi
      - Stesse quantità
      - Stessi sconti (percentuali e importi)
      - Stessa IVA
      - Stesso peso
    
    ### Totali
    - `total_price_with_tax`: Stesso totale del preventivo originale
    - `total_weight`: Stesso peso totale
    
    ## Il nuovo preventivo avrà
    
    - **document_number**: Nuovo numero sequenziale automatico
    - **type_document**: "preventivo"
    - **date_add**: Data di creazione corrente
    - **updated_at**: Data di creazione corrente
    - **id_order**: null (non collegato ad alcun ordine)
    - **note**: "Copia di {numero_originale}" + note originali (se presenti)
    
    ## Validazioni
    
    - Il preventivo originale deve esistere
    - Il preventivo originale deve essere di tipo "preventivo"
    
    ## Note
    
    - La spedizione viene **riutilizzata** (stesso ID), non duplicata
    - Customer e indirizzi vengono **riutilizzati** (stessi ID)
    - Il sezionale viene **riutilizzato** (stesso ID)
    - Tutti gli articoli vengono **copiati** come nuovi record
    - Il nuovo preventivo è completamente indipendente dall'originale
    """
    try:
        service = get_preventivo_service(db)
        result = service.duplicate_preventivo(id_order_document, user["id"])
        
        if not result:
            raise HTTPException(status_code=404, detail="Preventivo non trovato")
        
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.post("/{id_order_document}/convert-to-order", status_code=status.HTTP_200_OK,
             response_description="Preventivo convertito in ordine con successo")
async def convert_to_order(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Converte preventivo in ordine
    
    Converte automaticamente un preventivo in un ordine trasferendo tutti i dati.
    
    ## Dati Trasferiti
    
    ### Informazioni Base
    - **Customer**: ID cliente dal preventivo
    - **Indirizzi**: Consegna e fatturazione dal preventivo
    - **Sectional**: Sezionale dal preventivo (se presente)
    - **Reference**: Generata automaticamente come `PRV{document_number}`
    
    ### Articoli
    - Tutti gli articoli vengono **copiati** mantenendo:
      - Prezzi originali
      - Quantità
      - Sconti applicati
      - IVA
    
    ### Spedizione
    - Se il preventivo ha `id_shipping`, viene **riutilizzato** nell'ordine
    - **NON** viene creata una nuova spedizione (riutilizzo oggetto esistente)
    
    ### Totali
    - `total_price_with_tax`: Copiato dal preventivo (già con IVA inclusa)
    - `total_weight`: Copiato dal preventivo
    
    ## L'ordine creato avrà
    
    - **id_order_state**: 1 (pending)
    - **id_platform**: 1 (default)
    - **id_sectional**: Ereditato dal preventivo (se presente)
    - **id_shipping**: Ereditato dal preventivo (se presente)
    - **reference**: PRV{document_number}
    - **is_payed**: false
    - **id_payment**: null (da configurare successivamente)
    
    ## Validazioni
    
    - Il preventivo deve esistere
    - Il preventivo NON deve essere già stato convertito (controllo automatico)
    
    ## Note
    
    - La spedizione viene **riutilizzata**, non duplicata
    - Gli articoli vengono copiati mantenendo tutti i dettagli
    - Il preventivo rimane nel database e viene collegato all'ordine tramite `id_order`
    - Non puoi convertire lo stesso preventivo due volte
    """
    try:
        service = get_preventivo_service(db)
        result = service.convert_to_order(id_order_document, user["id"])
        
        if not result:
            raise HTTPException(status_code=404, detail="Preventivo non trovato")
        
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")
