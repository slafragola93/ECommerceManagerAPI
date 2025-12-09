from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from sqlalchemy.orm import Session
from src.database import get_db
from src.services.routers.auth_service import get_current_user, authorize
from src.services.core.wrap import check_authentication
from src.services.routers.ddt_service import DDTService
from src.schemas.ddt_schema import (
    DDTCreatePartialRequestSchema,
    DDTCreatePartialResponseSchema,
    DDTListResponseSchema,
    DDTCreateRequestSchema,
    DDTCreateResponseSchema,
    DDTMergeRequestSchema,
    DDTMergeResponseSchema,
    DDTResponseSchema,
    DDTGenerateResponseSchema
)
from src.schemas.preventivo_schema import ArticoloPreventivoUpdateSchema
from fastapi.responses import StreamingResponse
from io import BytesIO
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT

router = APIRouter(
    prefix="/api/v1/ddt",
    tags=["DDT"]
)

# Dependency per servizio DDT
def get_ddt_service(db: Session = Depends(get_db)) -> DDTService:
    return DDTService(db)

# Dependency per utente autenticato
user_dependency = Depends(get_current_user)
db_dependency = Depends(get_db)


@router.post("/create-partial",
             response_model=DDTCreatePartialResponseSchema,
             status_code=status.HTTP_201_CREATED,
             summary="Crea DDT parziale da articoli ordine",
             description="Crea un DDT parziale a partire da uno o più articoli ordine con quantità specificate. Recupera automaticamente RDA e rda_quantity se presenti.")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['C'])
async def create_ddt_partial(
    request: DDTCreatePartialRequestSchema = Body(...),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Crea un DDT parziale da uno o più articoli ordine.
    
    **Comportamento:**
    - Recupera gli articoli ordine originali
    - Per ogni articolo: se presente rda_quantity, usa quella come quantità, altrimenti usa quantity passata
    - Crea nuovo DDT con mittente da AppConfiguration
    - Include tutti gli articoli specificati con le quantità indicate
    """
    service = get_ddt_service(db)
    result = service.create_ddt_partial_from_order_details(
        articoli_data=request.articoli,
        user_id=user["id"],
        user=user
    )
    return result


@router.get("/",
            response_model=DDTListResponseSchema,
            status_code=status.HTTP_200_OK,
            summary="Lista DDT essenziali",
            description="Recupera lista DDT con solo informazioni essenziali (mittente e articoli). Stessi filtri dei preventivi.")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_ddt_list(
    page: int = Query(1, ge=1, description="Numero pagina (min: 1)"),
    limit: int = Query(100, ge=1, le=1000, description="Elementi per pagina (max: 1000)"),
    search: Optional[str] = Query(None, description="Ricerca per document_number o note"),
    sectionals_ids: Optional[str] = Query(None, description="ID sezionali separati da virgole (es: 1,2,3)"),
    payments_ids: Optional[str] = Query(None, description="ID pagamenti separati da virgole (es: 1,2,3)"),
    date_from: Optional[str] = Query(None, description="Data inizio filtro (formato: YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Data fine filtro (formato: YYYY-MM-DD)"),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Lista DDT con informazioni essenziali.
    
    **Filtri disponibili:**
    - `search`: Cerca in document_number o note
    - `sectionals_ids`: ID sezionali separati da virgole
    - `payments_ids`: ID pagamenti separati da virgole
    - `date_from`: Data inizio filtro
    - `date_to`: Data fine filtro
    
    **Risposta include:**
    - Informazioni essenziali DDT (id, numero, data)
    - Customer (solo id e nome)
    - Lista articoli essenziali (id, nome, riferimento, quantità)
    """
    service = get_ddt_service(db)
    skip = (page - 1) * limit
    result = service.get_ddt_list(
        skip=skip,
        limit=limit,
        search=search,
        sectionals_ids=sectionals_ids,
        payments_ids=payments_ids,
        date_from=date_from,
        date_to=date_to
    )
    return result


@router.post("/",
             response_model=DDTCreateResponseSchema,
             status_code=status.HTTP_201_CREATED,
             summary="Crea DDT normale",
             description="Crea un DDT normalmente. Verifica che non esista già un DDT con lo stesso numero documento.")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['C'])
async def create_ddt(
    request: DDTCreateRequestSchema = Body(...),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Crea un DDT normale.
    
    **Note:**
    - Permette di creare più DDT per lo stesso ordine
    - Usa mittente da AppConfiguration se configurato
    - Genera automaticamente document_number sequenziale
    """
    service = get_ddt_service(db)
    result = service.create_ddt(
        data=request,
        user_id=user["id"],
        user=user
    )
    return result


@router.post("/merge-articolo",
             response_model=DDTMergeResponseSchema,
             status_code=status.HTTP_200_OK,
             summary="Accorpa articolo a DDT esistente",
             description="Aggiunge un articolo a un DDT esistente. Se l'articolo esiste già, somma la quantità.")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['U'])
async def merge_articolo_to_ddt(
    request: DDTMergeRequestSchema = Body(...),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Accorpa un articolo a un DDT esistente.
    
    **Comportamento:**
    - Se l'articolo (stesso id_product o product_reference) esiste già nel DDT, somma la quantità
    - Se l'articolo non esiste, crea una nuova riga
    - Ricalcola automaticamente i totali del DDT
    - Verifica che il DDT sia modificabile (ordine non fatturato/spedito)
    """
    service = get_ddt_service(db)
    result = service.merge_articolo_to_ddt(
        id_order_document=request.id_order_document,
        id_order_detail=request.id_order_detail,
        quantity=request.quantity,
        user=user
    )
    return result


@router.post("/generate-from-order/{id_order}",
             response_model=DDTGenerateResponseSchema,
             status_code=status.HTTP_201_CREATED,
             summary="Genera DDT completo da ordine",
             description="Genera un Documento di Trasporto (DDT) completo a partire da tutti gli articoli di un ordine esistente.")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['C'])
async def generate_ddt_from_order(
    id_order: int = Path(..., gt=0, description="ID dell'ordine da cui generare il DDT"),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Genera un DDT (Documento di Trasporto) completo da un ordine esistente.
    
    **Comportamento:**
    - Crea un DDT con tutti gli articoli dell'ordine
    - Copia tutti i dati dell'ordine (cliente, indirizzi, spedizione, ecc.)
    - Genera automaticamente il numero documento sequenziale
    - Usa mittente da AppConfiguration se configurato
    
    **Note:**
    - Permette di creare più DDT per lo stesso ordine
    - Non verifica se esiste già un DDT per l'ordine
    """
    service = get_ddt_service(db)
    result = service.generate_ddt_from_order(id_order, user["id"], user)
    
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message
        )
    
    return result


@router.get("/pdf/{id_order_document}",
            status_code=status.HTTP_200_OK,
            summary="Genera PDF DDT",
            description="Genera il PDF del Documento di Trasporto (DDT) specificato",
            response_description="File PDF del DDT")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['R'])
async def generate_ddt_pdf(
    id_order_document: int = Path(..., gt=0, description="ID del DDT"),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Genera il PDF del DDT specificato.
    
    **Comportamento:**
    - Verifica che il DDT esista
    - Genera il PDF con tutti i dettagli del DDT
    - Restituisce il file PDF come download
    
    **Risposta:**
    - File PDF con nome `DDT-{document_number}.pdf`
    """
    service = get_ddt_service(db)
    
    # Verifica che il DDT esista
    ddt = service.get_ddt_complete(id_order_document)
    if not ddt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DDT non trovato"
        )
    
    # Genera il PDF
    pdf_content = service.generate_ddt_pdf(id_order_document)
    
    # Crea un buffer per il PDF
    pdf_buffer = BytesIO(pdf_content)
    
    # Determina nome file
    filename = f"DDT-{ddt.document_number}.pdf"
    
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


@router.get("/{id_order_document}",
            response_model=DDTResponseSchema,
            status_code=status.HTTP_200_OK,
            summary="Dettaglio DDT completo",
            description="Recupera un DDT completo con tutti i dettagli, inclusi cliente, indirizzi, spedizione, articoli e pacchi.")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE'], permissions_required=['R'])
async def get_ddt_detail(
    id_order_document: int = Path(..., gt=0, description="ID del DDT"),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Recupera un DDT completo con tutti i dettagli.
    
    **Include:**
    - Informazioni base del DDT (numero, data, note)
    - Dati cliente completo
    - Indirizzi di consegna e fatturazione
    - Dati spedizione
    - Lista completa articoli con dettagli
    - Lista pacchi (se presenti)
    - Dati mittente
    - Flag is_modifiable
    """
    service = get_ddt_service(db)
    ddt = service.get_ddt_complete(id_order_document)
    
    if not ddt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DDT non trovato"
        )
    
    return ddt


@router.put("/articoli/{id_order_detail}",
           status_code=status.HTTP_200_OK,
           summary="Aggiorna articolo DDT",
           description="Aggiorna un articolo collegato a un DDT. L'articolo deve essere collegato a un DDT e il DDT deve essere modificabile.",
           response_description="Articolo DDT aggiornato con successo")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['U'])
async def update_ddt_articolo(
    id_order_detail: int = Path(..., gt=0, description="ID dell'articolo"),
    articolo_data: ArticoloPreventivoUpdateSchema = Body(...),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Aggiorna un articolo in un DDT.
    
    **Campi Modificabili:**
    - **product_name**: Nome del prodotto (max 100 caratteri)
    - **product_reference**: Riferimento del prodotto (max 100 caratteri)
    - **unit_price_net**: Prezzo unitario senza IVA
    - **total_price_with_tax**: Totale con IVA
    - **product_weight**: Peso del prodotto (deve essere >= 0)
    - **product_qty**: Quantità del prodotto (deve essere > 0)
    - **id_tax**: ID dell'aliquota IVA (deve esistere)
    - **reduction_percent**: Sconto percentuale (deve essere >= 0)
    - **reduction_amount**: Sconto in importo (deve essere >= 0)
    - **rda**: Codice RDA (max 10 caratteri)
    - **rda_quantity**: Quantità da restituire
    - **note**: Note per l'articolo (max 200 caratteri)
    
    **Validazioni:**
    - Tutti i campi sono opzionali (solo i campi forniti vengono aggiornati)
    - L'articolo deve esistere ed essere collegato a un DDT
    - Il DDT deve essere modificabile (ordine non fatturato e non spedito)
    - La tassa specificata deve esistere nel sistema
    - I totali del DDT vengono ricalcolati automaticamente
    - I prezzi unitari vengono ricalcolati automaticamente se vengono modificati i totali
    
    **Note:**
    - Il ricalcolo automatico include: total_price_with_tax, total_weight
    - I prezzi unitari (unit_price_net, unit_price_with_tax) sono sempre al pezzo singolo
    - Il timestamp updated_at del DDT viene aggiornato automaticamente
    """
    from src.services.routers.order_document_service import OrderDocumentService
    from src.models.order_detail import OrderDetail
    from src.models.order_document import OrderDocument
    
    order_doc_service = OrderDocumentService(db)
    
    # Verifica che l'articolo esista e sia collegato a un DDT
    order_detail = db.query(OrderDetail).filter(
        OrderDetail.id_order_detail == id_order_detail
    ).first()
    
    if not order_detail:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    
    # Verifica che sia collegato a un DDT
    order_document = db.query(OrderDocument).filter(
        OrderDocument.id_order_document == order_detail.id_order_document
    ).first()
    
    if not order_document or order_document.type_document != "DDT":
        raise HTTPException(status_code=400, detail="L'articolo non è collegato a un DDT")
    
    # Verifica che il DDT sia modificabile
    if order_document.id_order:
        is_modifiable = order_doc_service.is_ddt_modifiable(order_document.id_order)
        if not is_modifiable:
            raise HTTPException(
                status_code=400, 
                detail="Il DDT non può essere modificato: l'ordine è già stato fatturato o spedito"
            )
    
    # Aggiorna l'articolo
    updated_articolo = order_doc_service.update_articolo(
        id_order_detail, 
        articolo_data, 
        "DDT"
    )
    
    if not updated_articolo:
        raise HTTPException(status_code=404, detail="Errore durante l'aggiornamento dell'articolo")
    
    # Restituisci l'articolo aggiornato
    return {
        "id_order_detail": updated_articolo.id_order_detail,
        "product_name": updated_articolo.product_name,
        "product_reference": updated_articolo.product_reference,
        "unit_price_net": float(updated_articolo.unit_price_net) if updated_articolo.unit_price_net else None,
        "unit_price_with_tax": float(updated_articolo.unit_price_with_tax) if updated_articolo.unit_price_with_tax else None,
        "total_price_net": float(updated_articolo.total_price_net) if updated_articolo.total_price_net else None,
        "total_price_with_tax": float(updated_articolo.total_price_with_tax) if updated_articolo.total_price_with_tax else None,
        "product_qty": updated_articolo.product_qty,
        "product_weight": float(updated_articolo.product_weight) if updated_articolo.product_weight else None,
        "id_tax": updated_articolo.id_tax,
        "reduction_percent": float(updated_articolo.reduction_percent) if updated_articolo.reduction_percent else None,
        "reduction_amount": float(updated_articolo.reduction_amount) if updated_articolo.reduction_amount else None,
        "rda": updated_articolo.rda,
        "rda_quantity": updated_articolo.rda_quantity,
        "note": updated_articolo.note,
        "message": "Articolo DDT aggiornato con successo"
    }


@router.delete("/articoli/{id_order_detail}",
              status_code=status.HTTP_204_NO_CONTENT,
              summary="Elimina articolo DDT",
              description="Elimina un articolo collegato a un DDT. L'articolo deve essere collegato a un DDT e il DDT deve essere modificabile.")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['D'])
async def delete_ddt_articolo(
    id_order_detail: int = Path(..., gt=0, description="ID dell'articolo"),
    user: dict = user_dependency,
    db: Session = db_dependency
):
    """
    Elimina un articolo da un DDT.
    
    **Validazioni:**
    - L'articolo deve esistere ed essere collegato a un DDT
    - Il DDT deve essere modificabile (ordine non fatturato e non spedito)
    - I totali del DDT vengono ricalcolati automaticamente dopo l'eliminazione
    """
    from src.services.routers.ddt_service import DDTService
    service = DDTService(db)
    
    success = service.delete_ddt_detail(id_order_detail, user)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Articolo DDT non trovato o non eliminabile"
        )
    
    return None

