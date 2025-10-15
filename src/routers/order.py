from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from starlette import status
from sqlalchemy.orm import Session
from .dependencies import db_dependency, user_dependency, MAX_LIMIT, LIMIT_DEFAULT
from .. import OrderSchema
from ..schemas.order_schema import OrderResponseSchema, AllOrderResponseSchema, OrderIdSchema, OrderUpdateSchema
from ..schemas.preventivo_schema import ArticoloPreventivoUpdateSchema
from src.services.wrap import check_authentication
from ..repository.order_repository import OrderRepository
from ..services.auth import authorize
from ..models.relations.relations import orders_history
from src.database import get_db
from src.services.auth import get_current_user
from src.models.user import User

router = APIRouter(
    prefix='/api/v1/orders',
    tags=['Order'],
)


def get_repository(db: db_dependency) -> OrderRepository:
    return OrderRepository(db)


@router.get("/", 
           status_code=status.HTTP_200_OK,
           summary="Recupera lista ordini",
           description="Recupera una lista di ordini con filtri opzionali e possibilità di includere dettagli completi delle relazioni",
           response_description="Lista di ordini con metadati di paginazione")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_all_orders(user: user_dependency,
                        or_repo: OrderRepository = Depends(get_repository),
                        orders_ids: Optional[str] = Query(None, description="ID degli ordini, separati da virgole (es: 1,2,3)"),
                        customers_ids: Optional[str] = Query(None, description="ID dei clienti, separati da virgole (es: 1,2,3)"),
                        order_states_ids: Optional[str] = Query(None, description="ID degli stati ordine, separati da virgole (es: 1,2,3)"),
                        platforms_ids: Optional[str] = Query(None, description="ID delle piattaforme, separati da virgole (es: 1,2,3)"),
                        payments_ids: Optional[str] = Query(None, description="ID dei pagamenti, separati da virgole (es: 1,2,3)"),
                        is_payed: Optional[bool] = Query(None, description="Filtro per ordini pagati (true) o non pagati (false)"),
                        is_invoice_requested: Optional[bool] = Query(None, description="Filtro per ordini con fattura richiesta (true) o no (false)"),
                        date_from: Optional[str] = Query(None, description="Data inizio filtro (formato: YYYY-MM-DD)"),
                        date_to: Optional[str] = Query(None, description="Data fine filtro (formato: YYYY-MM-DD)"),
                        show_details: str = Query("false", description="Se 'true', include dettagli completi delle relazioni (customer, platform, payment, shipping, addresses, order_states, order_details)"),
                        page: int = Query(1, gt=0, description="Numero di pagina (inizia da 1)"),
                        limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT, description=f"Numero di elementi per pagina (max {MAX_LIMIT})")):
    """
    Recupera una lista di ordini con filtri opzionali e possibilità di includere dettagli completi.

    **Filtri disponibili:**
    - `orders_ids`: ID degli ordini specifici (es: "1,2,3")
    - `customers_ids`: ID dei clienti (es: "1,2,3") 
    - `order_states_ids`: ID degli stati ordine (es: "1,2,3")
    - `platforms_ids`: ID delle piattaforme (es: "1,2,3")
    - `payments_ids`: ID dei metodi di pagamento (es: "1,2,3")
    - `is_payed`: Filtro per ordini pagati (true) o non pagati (false)
    - `is_invoice_requested`: Filtro per ordini con fattura richiesta (true) o no (false)
    - `date_from`: Data inizio filtro (formato: YYYY-MM-DD)
    - `date_to`: Data fine filtro (formato: YYYY-MM-DD)

    **Parametro show_details:**
    - `show_details=false` (default): Restituisce solo i campi base con ID delle relazioni
    - `show_details=true`: Include dettagli completi delle entità correlate:
      - `customer`: Dettagli completi del cliente
      - `platform`: Dettagli della piattaforma
      - `payment`: Dettagli del metodo di pagamento
      - `shipping`: Dettagli della spedizione
      - `address_delivery`: Indirizzo di consegna completo
      - `address_invoice`: Indirizzo di fatturazione completo
      - `sectional`: Dettagli della sezione
      - `order_states`: Lista degli stati dell'ordine
      - `order_details`: Lista dei dettagli/articoli dell'ordine

    **Paginazione:**
    - `page`: Numero di pagina (inizia da 1)
    - `limit`: Numero di elementi per pagina (max 100)

    **Risposta:**
    ```json
    {
        "orders": [...],
        "total": 150,
        "page": 1,
        "limit": 20
    }
    ```

    **Esempi di utilizzo:**
    - `/orders` - Tutti gli ordini (risposta base)
    - `/orders?show_details=true` - Tutti gli ordini con dettagli completi
    - `/orders?customers_ids=1,2&show_details=true` - Ordini di clienti specifici con dettagli
    - `/orders?is_payed=true&date_from=2024-01-01` - Ordini pagati dal 1 gennaio 2024
    """
    
    orders = or_repo.get_all(orders_ids=orders_ids,
                            customers_ids=customers_ids,
                            order_states_ids=order_states_ids,
                            platforms_ids=platforms_ids,
                            payments_ids=payments_ids,
                            is_payed=is_payed,
                            is_invoice_requested=is_invoice_requested,
                            date_from=date_from,
                            date_to=date_to,
                            show_details=show_details,
                            page=page,
                            limit=limit)

    if not orders:
        raise HTTPException(status_code=404, detail="Nessun ordine trovato")

    total_count = or_repo.get_count(orders_ids=orders_ids,
                                   customers_ids=customers_ids,
                                   order_states_ids=order_states_ids,
                                   platforms_ids=platforms_ids,
                                   payments_ids=payments_ids,
                                   is_payed=is_payed,
                                   is_invoice_requested=is_invoice_requested,
                                   date_from=date_from,
                                   date_to=date_to)

    results = []
    for order in orders:
        results.append(or_repo.formatted_output(order, show_details=show_details))
    return {"orders": results, "total": total_count, "page": page, "limit": limit}



@router.get("/{order_id}", status_code=status.HTTP_200_OK, response_model=OrderIdSchema)
@check_authentication  
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])  
async def get_order_by_id(user: user_dependency,
                         or_repo: OrderRepository = Depends(get_repository),
                         order_id: int = Path(gt=0)):
    """
    Recupera un singolo ordine per ID con tutti i dettagli delle relazioni.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `order_id`: ID dell'ordine da recuperare.

    **Esempi di utilizzo:**
    - `/orders/123` - Ordine con tutti i dettagli completi

    **Risposta include sempre:**
    - Dettagli completi del cliente
    - Informazioni della piattaforma
    - Dettagli del metodo di pagamento
    - Informazioni di spedizione
    - Indirizzi di consegna e fatturazione completi
    - Stati dell'ordine
    - Dettagli dei prodotti ordinati
    """
    
    # Usa sempre il metodo ottimizzato per caricare tutte le relazioni
    order = or_repo.get_by_id(_id=order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Ordine non trovato")

    # Restituisce sempre i dettagli completi
    return or_repo.formatted_output(order, show_details=True)


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Ordine creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def create_order(user: user_dependency,
                       order: OrderSchema,
                       or_repo: OrderRepository = Depends(get_repository)):
    """
    Crea un nuovo ordine con i dati forniti.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `order`: Schema dell'ordine da creare.
    """
    return or_repo.create(data=order)


@router.put("/{order_id}", status_code=status.HTTP_200_OK, response_description="Ordine aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_order(user: user_dependency,
                      order_schema: OrderUpdateSchema,
                      or_repo: OrderRepository = Depends(get_repository),
                      order_id: int = Path(gt=0)):
    """
    Aggiorna un ordine esistente con aggiornamenti parziali.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `order_schema`: Schema dell'ordine con i campi da aggiornare (tutti opzionali).
    - `order_id`: ID dell'ordine da aggiornare.
    
    Esempio di aggiornamento parziale:
    ```json
    {
        "is_payed": true,
        "payment_date": "2025-01-15T10:30:00"
    }
    ```
    """
    order = or_repo.get_by_id(_id=order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Ordine non trovato")

    or_repo.update(edited_order=order, data=order_schema)


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Ordine eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
async def delete_order(user: user_dependency,
                      or_repo: OrderRepository = Depends(get_repository),
                      order_id: int = Path(gt=0)):
    """
    Elimina un ordine dal sistema per l'ID specificato.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `order_id`: ID dell'ordine da eliminare.
    """
    order = or_repo.get_by_id(_id=order_id)

    if order is None:
        raise HTTPException(status_code=404, detail="Ordine non trovato")

    or_repo.delete(order=order)


# Endpoint aggiuntivi per la gestione degli ordini

@router.patch("/{order_id}/status", status_code=status.HTTP_200_OK, response_description="Stato ordine aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['U'])
async def update_order_status(user: user_dependency,
                             or_repo: OrderRepository = Depends(get_repository),
                             order_id: int = Path(gt=0),
                             new_status_id: int = Query(gt=0)):
    """
    Aggiorna lo stato di un ordine e crea un record nell'order history.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `order_id`: ID dell'ordine da aggiornare.
    - `new_status_id`: ID del nuovo stato dell'ordine.
    
    La funzione aggiorna lo stato dell'ordine nella tabella orders e crea
    un nuovo record nella tabella orders_history per tracciare il cambio di stato.
    """
    order = or_repo.get_by_id(_id=order_id)

    if order is None:
        raise HTTPException(status_code=404, detail="Ordine non trovato")

    # Aggiorna solo lo stato dell'ordine
    order.id_order_state = new_status_id
    or_repo.session.add(order)
    
    # Aggiungi record nell'order history con data e ora
    from datetime import datetime
    order_history_insert = orders_history.insert().values(
        id_order=order_id,
        id_order_state=new_status_id,
        date_add=datetime.now()
    )
    or_repo.session.execute(order_history_insert)
    
    or_repo.session.commit()

    return {"message": "Stato ordine aggiornato con successo", "order_id": order_id, "new_status_id": new_status_id}


@router.patch("/{order_id}/payment", status_code=status.HTTP_200_OK, response_description="Stato pagamento aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['U'])
async def update_order_payment(user: user_dependency,
                              or_repo: OrderRepository = Depends(get_repository),
                              order_id: int = Path(gt=0),
                              is_payed: bool = Query()):
    """
    Aggiorna lo stato di pagamento di un ordine.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `order_id`: ID dell'ordine da aggiornare.
    - `is_payed`: Nuovo stato di pagamento (true/false).
    """
    order = or_repo.get_by_id(_id=order_id)

    if order is None:
        raise HTTPException(status_code=404, detail="Ordine non trovato")

    # Aggiorna lo stato di pagamento
    order.is_payed = is_payed
    if is_payed:
        from datetime import datetime
        order.payment_date = datetime.now()
    
    or_repo.session.add(order)
    or_repo.session.commit()

    return {"message": "Stato pagamento aggiornato con successo", "order_id": order_id, "is_payed": is_payed}


@router.post("/{id_order}/generate-ddt",
             status_code=status.HTTP_201_CREATED,
             summary="Genera DDT da ordine",
             description="Genera un Documento di Trasporto (DDT) a partire da un ordine esistente. Il DDT può essere generato solo se l'ordine non è stato fatturato e non è stato spedito.",
             response_description="DDT generato con successo")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['C'])
async def generate_ddt_from_order(
    id_order: int = Path(..., description="ID dell'ordine da cui generare il DDT"),
    user: user_dependency = None,
    or_repo: OrderRepository = Depends(get_repository)
):
    """
    Genera un DDT (Documento di Trasporto) da un ordine esistente
    
    Args:
        id_order: ID dell'ordine da cui generare il DDT
        user: Utente autenticato
        or_repo: Repository degli ordini
        
    Returns:
        dict: Risposta con il DDT generato
        
    Raises:
        HTTPException: Se l'ordine non esiste o non può essere convertito in DDT
    """
    try:
        # Importa il DDTService
        from src.services.ddt_service import DDTService
        ddt_service = DDTService(or_repo.session)
        
        # Genera il DDT
        result = ddt_service.generate_ddt_from_order(id_order, user["id"])
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.message
            )
        
        return {
            "message": result.message,
            "ddt": result.ddt.dict() if result.ddt else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore interno: {str(e)}"
        )


@router.get("/generate-ddt-pdf/{id_order_document}",
            status_code=status.HTTP_200_OK,
            summary="Genera PDF DDT",
            description="Genera il PDF del Documento di Trasporto (DDT) specificato",
            response_description="File PDF del DDT")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['R'])
async def generate_ddt_pdf(
    id_order_document: int = Path(..., description="ID del DDT"),
    user: user_dependency = None,
    or_repo: OrderRepository = Depends(get_repository)
):
    """
    Genera il PDF del DDT specificato
    
    Args:
        id_order_document: ID del DDT
        user: Utente autenticato
        or_repo: Repository degli ordini
        
    Returns:
        Response: File PDF del DDT
        
    Raises:
        HTTPException: Se il DDT non esiste
    """
    try:
        # Importa il DDTService
        from src.services.ddt_service import DDTService
        ddt_service = DDTService(or_repo.session)
        
        # Verifica che il DDT esista
        ddt = ddt_service.get_ddt_complete(id_order_document)
        if not ddt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DDT non trovato"
            )
        
        # Genera il PDF
        pdf_content = ddt_service.generate_ddt_pdf(id_order_document)
        
        # Restituisce il PDF come risposta
        from fastapi.responses import StreamingResponse
        from io import BytesIO
        
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
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore interno: {str(e)}"
        )


@router.put("/ddt/articoli/{id_order_detail}",
           status_code=status.HTTP_200_OK,
           summary="Aggiorna articolo DDT",
           description="Aggiorna un articolo collegato a un DDT. L'articolo deve essere collegato a un DDT e l'ordine associato non deve essere fatturato o spedito.",
           response_description="Articolo DDT aggiornato con successo")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['U'])
async def update_ddt_articolo(
    id_order_detail: int = Path(..., gt=0, description="ID dell'articolo"),
    articolo_data: ArticoloPreventivoUpdateSchema = ...,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Aggiorna un articolo in un DDT
    
    ## Descrizione
    
    Questo endpoint permette di modificare un order_detail collegato a un DDT.
    Il sistema ricalcola automaticamente i totali del DDT dopo la modifica.
    
    ## Campi Modificabili
    
    Puoi aggiornare tutti i seguenti campi dell'articolo:
    
    ### Informazioni Prodotto
    - **product_name**: Nome del prodotto (max 100 caratteri)
    - **product_reference**: Riferimento del prodotto (max 100 caratteri)
    - **product_price**: Prezzo del prodotto (deve essere > 0)
    - **product_weight**: Peso del prodotto (deve essere >= 0)
    - **product_qty**: Quantità del prodotto (deve essere > 0)
    
    ### Tassazione e Sconti
    - **id_tax**: ID dell'aliquota IVA (deve esistere)
    - **reduction_percent**: Sconto percentuale (deve essere >= 0)
    - **reduction_amount**: Sconto in importo (deve essere >= 0)
    
    ### Altri Campi
    - **rda**: Codice RDA (max 10 caratteri)
    
    ## Validazioni
    
    - Tutti i campi sono opzionali (solo i campi forniti vengono aggiornati)
    - L'articolo deve esistere ed essere collegato a un DDT
    - Il DDT deve essere modificabile (ordine non fatturato e non spedito)
    - La tassa specificata deve esistere nel sistema
    - I totali del DDT vengono ricalcolati automaticamente
    
    ## Esempio
    
    ```json
    {
        "product_name": "Prodotto aggiornato",
        "product_price": 150.50,
        "product_qty": 2,
        "id_tax": 1,
        "reduction_percent": 10.0
    }
    ```
    
    ## Note
    
    - Il ricalcolo automatico include: total_price_with_tax, total_weight
    - La modifica è permessa solo se l'ordine collegato non è stato fatturato o spedito
    - Il timestamp updated_at del DDT viene aggiornato automaticamente
    """
    try:
        from src.services.order_document_service import OrderDocumentService
        order_doc_service = OrderDocumentService(db)
        
        # Verifica che l'articolo esista e sia collegato a un DDT
        from src.models.order_detail import OrderDetail
        from src.models.order_document import OrderDocument
        
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
            "product_price": updated_articolo.product_price,
            "product_qty": updated_articolo.product_qty,
            "product_weight": updated_articolo.product_weight,
            "id_tax": updated_articolo.id_tax,
            "reduction_percent": updated_articolo.reduction_percent,
            "reduction_amount": updated_articolo.reduction_amount,
            "rda": updated_articolo.rda,
            "message": "Articolo DDT aggiornato con successo"
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


