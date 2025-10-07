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
            }
        }
    ),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Crea un nuovo preventivo
    
    ## Regole importanti:
    
    ### Customer e Address:
    - **customer**: OBBLIGATORIO - Passa `{"id": X}` per usare un customer esistente, oppure `{"data": {...}}` per crearne uno nuovo
    - **address_delivery**: OBBLIGATORIO - Passa `{"id": X}` per usare un indirizzo esistente, oppure `{"data": {...}}` per crearne uno nuovo
    - **address_invoice**: OPZIONALE - Se non specificato, verrà usato `address_delivery` anche come indirizzo di fatturazione
    
    ### Articoli:
    - **Con id_product**: Se specifichi `id_product`, verranno usati i dati del prodotto esistente (solo `product_qty` è obbligatorio)
    - **Senza id_product**: Per prodotti personalizzati, devi specificare `product_name`, `product_reference`, `product_price`, `product_qty`
    - **id_tax**: Sempre obbligatorio per ogni articolo
    - **Sconti**: Usa `reduction_percent` (%) o `reduction_amount` (importo fisso), non entrambi
    
    ### Calcolo totali:
    - Il totale viene calcolato automaticamente sommando (prezzo * quantità) di ogni articolo
    - Gli sconti vengono applicati per riga
    - La tassa viene applicata al totale finale (non per singolo articolo)
    
    ### Reference:
    - La reference viene generata automaticamente nel formato `PRV{document_number}`
    - Non è necessario specificarla
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
    """Aggiorna preventivo"""
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


@router.put("/{id_order_document}/articoli/{id_order_detail}", response_model=ArticoloPreventivoSchema,
            response_description="Articolo aggiornato con successo")
async def update_articolo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
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


@router.delete("/{id_order_document}/articoli/{id_order_detail}", status_code=status.HTTP_204_NO_CONTENT,
               response_description="Articolo rimosso con successo")
async def remove_articolo(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
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


@router.post("/{id_order_document}/convert-to-order", status_code=status.HTTP_200_OK,
             response_description="Preventivo convertito in ordine con successo")
async def convert_to_order(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """
    Converte preventivo in ordine
    
    Converte automaticamente un preventivo in un ordine usando:
    - Dati del cliente e indirizzi dal preventivo
    - Articoli dal preventivo
    - Valori di default per campi non specificati nel preventivo
    
    L'ordine creato avrà:
    - Stato: "pending" (id_order_state = 1)
    - Piattaforma: default (id_platform = 1)
    - Pagamento/Spedizione: da configurare successivamente
    - Reference: generata automaticamente (PRV{document_number})
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


@router.get("/{id_order_document}/totali", status_code=status.HTTP_200_OK,
            response_description="Totali calcolati con successo")
async def get_totals(
    id_order_document: int = Path(..., gt=0, description="ID del preventivo"),
    user: User = user_dependency,
    db: Session = db_dependency
):
    """Recupera totali calcolati del preventivo"""
    try:
        service = get_preventivo_service(db)
        totals = service.get_totals(id_order_document)
        
        if not totals:
            raise HTTPException(status_code=404, detail="Preventivo non trovato")
        
        return totals
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")
