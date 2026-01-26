"""
Router per gestione ordini seguendo principi SOLID.
Tutte le funzioni helper e la logica business sono nel service.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Body
from sqlalchemy.orm import Session
from starlette import status

from src.database import get_db
from src.repository.order_detail_repository import OrderDetailRepository
from src.repository.product_repository import ProductRepository
from src.routers.dependencies import get_fiscal_document_service
from src.services.core.wrap import check_authentication
from src.services.interfaces.fiscal_document_service_interface import IFiscalDocumentService
from src.services.routers.auth_service import authorize, get_current_user
from src.services.routers.product_service import ProductService

from .. import OrderSchema
from ..repository.order_repository import OrderRepository
from typing import List
from ..schemas.order_schema import (
    OrderIdSchema, 
    OrderUpdateSchema,
    OrderStatusUpdateItem,
    BulkOrderStatusUpdateResponseSchema
)
from src.services.routers.order_service import OrderService
from src.services.interfaces.order_service_interface import IOrderService
from ..schemas.order_detail_schema import OrderDetailCreateSchema, OrderDetailUpdateSchema, OrderDetailResponseSchema
from ..schemas.return_schema import (
    AllReturnsResponseSchema,
    ReturnCreateSchema,
    ReturnDetailUpdateSchema,
    ReturnResponseSchema,
    ReturnUpdateSchema,
)
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix='/api/v1/orders',
    tags=['Order'],
)



def get_repository(db: Session = Depends(get_db)) -> OrderRepository:
    """Dependency injection per Order Repository."""
    return OrderRepository(db)


def get_order_detail_repository(db: Session = Depends(get_db)) -> OrderDetailRepository:
    """Dependency injection per Order Detail Repository."""
    return OrderDetailRepository(db)

def get_order_service(db: Session = Depends(get_db)) -> IOrderService:
    """Dependency injection per Order Service."""
    order_repo = OrderRepository(db)
    return OrderService(order_repo)

def get_product_service(db: Session = Depends(get_db)) -> ProductService:
    """Dependency injection per Product Service."""
    product_repo = ProductRepository(db)
    return ProductService(product_repo)

@router.get("/", 
           status_code=status.HTTP_200_OK,
           summary="Recupera lista ordini",
           description="Recupera una lista di ordini con filtri opzionali e possibilità di includere dettagli completi delle relazioni",
           response_description="Lista di ordini con metadati di paginazione")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_all_orders(user: dict = Depends(get_current_user),
                        or_repo: OrderRepository = Depends(get_repository),
                        orders_ids: Optional[str] = Query(None, description="ID degli ordini, separati da virgole (es: 1,2,3)"),
                        customers_ids: Optional[str] = Query(None, description="ID dei clienti, separati da virgole (es: 1,2,3)"),
                        order_states_ids: Optional[str] = Query(None, description="ID degli stati ordine, separati da virgole (es: 1,2,3)"),
                        shipping_states_ids: Optional[str] = Query(None, description="ID degli stati spedizione, separati da virgole (es: 1,2,3)"),
                        delivery_countries_ids: Optional[str] = Query(None, description="ID dei paesi di consegna, separati da virgole (es: 1,2,3)"),
                        platforms_ids: Optional[str] = Query(None, description="ID delle piattaforme, separati da virgole (es: 1,2,3)"),
                        stores_ids: Optional[str] = Query(None, description="ID degli store, separati da virgole (es: 1,2,3)"),
                        payments_ids: Optional[str] = Query(None, description="ID dei pagamenti, separati da virgole (es: 1,2,3)"),
                        ecommerce_states_ids: Optional[str] = Query(None, description="ID degli stati e-commerce, separati da virgole (es: 1,2,3)"),
                        search: Optional[str] = Query(None, description="Ricerca rapida in vari campi (reference, internal_reference, customer, address, payment, products, tracking)"),
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
    - `shipping_states_ids`: ID degli stati spedizione (es: "1,2,3")
    - `delivery_countries_ids`: ID dei paesi di consegna (es: "1,2,3")
    - `stores_ids`: ID degli store (es: "1,2,3")
    - `payments_ids`: ID dei metodi di pagamento (es: "1,2,3")
    - `ecommerce_states_ids`: ID degli stati e-commerce (es: "1,2,3")
    - `search`: Ricerca rapida in vari campi (reference, internal_reference, customer, address, payment, products, tracking)
    - `is_payed`: Filtro per ordini pagati (true) o non pagati (false)
    - `is_invoice_requested`: Filtro per ordini con fattura richiesta (true) o no (false)
    - `date_from`: Data inizio filtro (formato: YYYY-MM-DD)
    - `date_to`: Data fine filtro (formato: YYYY-MM-DD)

    **Parametro show_details:**
    - `show_details=false` (default): Restituisce solo i campi base con ID delle relazioni
    - `show_details=true`: Include dettagli completi delle entità correlate:
      - `customer`: Dettagli completi del cliente
      - `store`: Dettagli dello store
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
                            shipping_states_ids=shipping_states_ids,
                            delivery_countries_ids=delivery_countries_ids,
                            platforms_ids=platforms_ids,
                            store_ids=stores_ids,
                            payments_ids=payments_ids,
                            ecommerce_states_ids=ecommerce_states_ids,
                            search=search,
                            is_payed=is_payed,
                            is_invoice_requested=is_invoice_requested,
                            date_from=date_from,
                            date_to=date_to,
                            show_details=show_details == "true",
                            page=page,
                            limit=limit)
    
    if not orders:
        raise HTTPException(status_code=404, detail="Nessun ordine trovato")

    total_count = or_repo.get_count(orders_ids=orders_ids,
                                   customers_ids=customers_ids,
                                   order_states_ids=order_states_ids,
                                   shipping_states_ids=shipping_states_ids,
                                   delivery_countries_ids=delivery_countries_ids,
                                   platforms_ids=platforms_ids,
                                   store_ids=stores_ids,
                                   payments_ids=payments_ids,
                                   ecommerce_states_ids=ecommerce_states_ids,
                                   search=search,
                                   is_payed=is_payed,
                                   is_invoice_requested=is_invoice_requested,
                                   date_from=date_from,
                                   date_to=date_to)

    results = []
    for order in orders:
        results.append(or_repo.formatted_output(order, show_details=show_details == "true", include_order_history=False))
    return {"orders": results, "total": total_count, "page": page, "limit": limit}


@router.get("/{order_id}", status_code=status.HTTP_200_OK, response_model=OrderIdSchema)
@check_authentication  
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])  
async def get_order_by_id(order_id: int = Path(gt=0),
                         user: dict = Depends(get_current_user),
                         or_repo: OrderRepository = Depends(get_repository)):
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


@router.get("/{order_id}/history", status_code=status.HTTP_200_OK, summary="Storico stato ordine")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_order_history(
    order_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    or_repo: OrderRepository = Depends(get_repository),
):
    """Restituisce la cronologia in formato [{state, data}]"""
    return or_repo.get_order_history_by_id_order(order_id)


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Ordine creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def create_order(
    order: OrderSchema,
    user: dict = Depends(get_current_user),
    order_service: IOrderService = Depends(get_order_service)
):
    """
    Crea un nuovo ordine con i dati forniti.
    
    **Features**:
    - Crea ordine nel database
    - Emette evento ORDER_CREATED
    - Stock plugin decrementa automaticamente product.quantity
    - Calcola totali automaticamente

    **Parametri**:
    - `user`: Utente autenticato
    - `order`: Schema dell'ordine con customer, addresses, shipping, order_details
    
    **Eventi emessi**: ORDER_CREATED (attiva plugin stock e altri futuri plugin)
    """
    created_order = await order_service.create_order(order, user=user)
    
    return {
        "message": "Ordine creato con successo",
        "id_order": created_order.id_order,
        "internal_reference": created_order.internal_reference,
        "total_price_with_tax": float(created_order.total_price_with_tax or 0)
    }


@router.put("/{order_id}", status_code=status.HTTP_200_OK, response_description="Ordine aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_order(
    order_schema: OrderUpdateSchema,
    order_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    order_service: IOrderService = Depends(get_order_service)
):
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
    
    Gli eventi ORDER_STATUS_CHANGED vengono emessi automaticamente dal decorator
    nel service se lo stato viene modificato.
    """
    return await order_service.update_order(order_id, order_schema)


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT, response_description="Ordine eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
async def delete_order(order_id: int = Path(gt=0),
                      user: dict = Depends(get_current_user),
                      order_service: IOrderService = Depends(get_order_service)):
    """
    Elimina un ordine dal sistema per l'ID specificato.
    
    L'ordine può essere eliminato solo se:
    - È in stato iniziale (id_order_state = 1, "In Preparazione")
    - Non ha documenti fiscali collegati
    
    Vengono eliminati:
    - Order
    - OrderDetail collegati
    - OrderPackage collegati
    
    Vengono lasciati intatti:
    - FiscalDocument (se presenti, l'eliminazione fallisce)
    - OrderDocument (id_order diventerà NULL)

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `order_id`: ID dell'ordine da eliminare.
    """
    await order_service.delete_order(order_id, user=user)




@router.patch("/{order_id}/status", status_code=status.HTTP_200_OK, response_description="Stato ordine aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['U'])
async def update_order_status(
    order_id: int = Path(gt=0),
    new_status_id: int = Query(gt=0),
    user: dict = Depends(get_current_user),
    order_service: IOrderService = Depends(get_order_service)
):
    """
    Aggiorna lo stato di un ordine e crea un record nell'order history.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `order_id`: ID dell'ordine da aggiornare.
    - `new_status_id`: ID del nuovo stato dell'ordine.
    
    La funzione aggiorna lo stato dell'ordine nella tabella orders e crea
    un nuovo record nella tabella orders_history per tracciare il cambio di stato.
    
    Gli eventi ORDER_STATUS_CHANGED vengono emessi automaticamente dal decorator
    nel service se lo stato viene modificato.
    """
    try:
        return await order_service.update_order_status(order_id, new_status_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/bulk-status", 
             status_code=status.HTTP_200_OK, 
             response_model=BulkOrderStatusUpdateResponseSchema,
             response_description="Aggiornamento massivo stati ordini completato")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['U'])
async def bulk_update_order_status(
    updates: List[OrderStatusUpdateItem] = Body(..., description="Lista di aggiornamenti stato ordine"),
    user: dict = Depends(get_current_user),
    order_service: IOrderService = Depends(get_order_service)
):
    """
    Aggiorna gli stati di più ordini in modo massivo.
    
    Parametri:
    - `updates`: Lista di aggiornamenti stato con `id_order` e `id_order_state`
    
    Per ogni ordine nella lista:
    - Verifica esistenza ordine
    - Verifica che lo stato sia diverso da quello corrente
    - Valida che lo stato esista nella tabella order_states
    - Se valido: aggiorna stato, crea record in orders_history, emette evento ORDER_STATUS_CHANGED
    - Se non valido: aggiunge a lista errori
    
    Restituisce risultati dettagliati con successi e fallimenti.
    
    Esempio di richiesta:
    ```json
    [
        {"id_order": 1, "id_order_state": 2},
        {"id_order": 2, "id_order_state": 2}
    ]
    ```
    
    Gli eventi ORDER_STATUS_CHANGED vengono emessi automaticamente dal decorator
    nel service per ogni cambio stato valido.
    """
    return await order_service.bulk_update_order_status(updates)


@router.patch("/{order_id}/payment", status_code=status.HTTP_200_OK, response_description="Stato pagamento aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['U'])
async def update_order_payment(order_id: int = Path(gt=0),
                              is_payed: bool = Query(),
                              user: dict = Depends(get_current_user),
                              or_repo: OrderRepository = Depends(get_repository)):
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


# ==================== ENDPOINT PER I RESI ====================

@router.post("/{id_order}/returns", 
            status_code=status.HTTP_201_CREATED,
            summary="Crea un reso per un ordine",
            description="Crea un nuovo documento di reso per un ordine specifico",
            response_description="Reso creato con successo")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['C'])
async def create_return(
    id_order: int = Path(..., description="ID dell'ordine"),
    user: dict = Depends(get_current_user),
    return_data: ReturnCreateSchema = None,
    fiscal_document_service: IFiscalDocumentService = Depends(get_fiscal_document_service)
):
    """
    Crea un nuovo reso per un ordine specifico.
    
    Il reso può includere:
    - Articoli specifici dell'ordine con quantità personalizzate
    - Spese di spedizione (opzionale)
    - Note aggiuntive
    
    Il sistema calcola automaticamente:
    - Il numero sequenziale del reso
    - Il totale con IVA inclusa
    - Se il reso è parziale o totale
    """

    # Verifica che l'ordine esista
    from src.models.order import Order
    from src.database import get_db
    db = next(get_db())
    order = db.query(Order).filter(Order.id_order == id_order).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Ordine {id_order} non trovato")
    
    # Crea il reso
    return_doc = await fiscal_document_service.create_return(id_order, return_data)
    
    return {
        "message": "Reso creato con successo",
        "return_document": ReturnResponseSchema.from_orm(return_doc),
        "return_id": return_doc.id_fiscal_document
    }
        



@router.get("/{id_order}/returns", 
           status_code=status.HTTP_200_OK,
           summary="Recupera i resi di un ordine",
           description="Recupera tutti i documenti di reso per un ordine specifico",
           response_description="Lista dei resi dell'ordine")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['R'])
async def get_order_returns(
    id_order: int = Path(..., description="ID dell'ordine"),
    user: dict = Depends(get_current_user),
    fiscal_document_service: IFiscalDocumentService = Depends(get_fiscal_document_service)
):
    """
    Recupera tutti i documenti di reso per un ordine specifico.
    """
    returns = await fiscal_document_service.get_fiscal_documents_by_order(id_order, 'return')
    
    return {
        "returns": [ReturnResponseSchema.from_orm(return_doc) for return_doc in returns],
        "total": len(returns),
        "order_id": id_order
    }



@router.put("/returns/{id_fiscal_document}", 
           status_code=status.HTTP_200_OK,
           summary="Aggiorna un reso",
           description="Aggiorna i dati di un documento di reso esistente",
           response_description="Reso aggiornato con successo")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['U'])
async def update_return(
    id_fiscal_document: int = Path(..., description="ID del documento di reso"),
    user: dict = Depends(get_current_user),
    update_data: ReturnUpdateSchema = None,
    fiscal_document_service: IFiscalDocumentService = Depends(get_fiscal_document_service)
):
    """
    Aggiorna un documento di reso esistente.
    
    Permette di modificare:
    - Lo stato del reso (pending, processed, cancelled)
    - Le note del reso
    - Se includere le spese di spedizione (con ricalcolo automatico del totale)
    """
    updated_return = await fiscal_document_service.update_fiscal_document(id_fiscal_document, update_data)
    
    return {
        "message": "Reso aggiornato con successo",
        "return_document": ReturnResponseSchema.from_orm(updated_return)
    }
    


@router.delete("/returns/{id_fiscal_document}", 
              status_code=status.HTTP_200_OK,
              summary="Elimina un reso",
              description="Elimina un documento di reso (solo se in stato pending)",
              response_description="Reso eliminato con successo")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['D'])
async def delete_return(
    id_fiscal_document: int = Path(..., description="ID del documento di reso"),
    user: dict = Depends(get_current_user),
    fiscal_document_service: IFiscalDocumentService = Depends(get_fiscal_document_service)
):
    """
    Elimina un documento di reso.
    
    Nota: Solo i resi in stato 'pending' possono essere eliminati.
    """
    return await fiscal_document_service.delete_fiscal_document(id_fiscal_document)



@router.put("/returns/details/{id_fiscal_document_detail}", 
           status_code=status.HTTP_200_OK,
           summary="Aggiorna un dettaglio di reso",
           description="Aggiorna quantità o prezzo di un singolo articolo nel reso",
           response_description="Dettaglio reso aggiornato con successo")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['U'])
async def update_return_detail(
    id_fiscal_document_detail: int = Path(..., description="ID del dettaglio di reso"),
    user: dict = Depends(get_current_user),
    update_data: ReturnDetailUpdateSchema = None,
    fiscal_document_service: IFiscalDocumentService = Depends(get_fiscal_document_service)
):
    """
    Aggiorna un singolo dettaglio (articolo) di un reso.
    
    Permette di modificare:
    - La quantità da restituire
    - Il prezzo unitario
    
    Il totale del reso viene ricalcolato automaticamente.
    """
    updated_detail = await fiscal_document_service.update_fiscal_document_detail(id_fiscal_document_detail, update_data)
    
    return {
        "message": "Dettaglio reso aggiornato con successo",
        "detail": updated_detail
    }
        


@router.delete("/returns/details/{id_fiscal_document_detail}", 
              status_code=status.HTTP_200_OK,
              summary="Elimina un dettaglio di reso",
              description="Elimina un singolo articolo dal reso",
              response_description="Dettaglio reso eliminato con successo")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['D'])
async def delete_return_detail(
    id_fiscal_document_detail: int = Path(..., description="ID del dettaglio di reso"),
    user: dict = Depends(get_current_user),
    fiscal_document_service: IFiscalDocumentService = Depends(get_fiscal_document_service)
):
    """
    Elimina un singolo dettaglio (articolo) da un reso.
    
    Il totale del reso viene ricalcolato automaticamente.
    """
    return await fiscal_document_service.delete_fiscal_document_detail(id_fiscal_document_detail)


@router.get("/returns/", 
           status_code=status.HTTP_200_OK,
           summary="Recupera tutti i resi",
           description="Recupera tutti i documenti di reso con paginazione",
           response_description="Lista di tutti i resi")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE'], permissions_required=['R'])
async def get_all_returns(
    user: dict = Depends(get_current_user),
    page: int = Query(1, gt=0, description="Numero di pagina"),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT, description=f"Numero di elementi per pagina (max {MAX_LIMIT})"),
    fiscal_document_service: IFiscalDocumentService = Depends(get_fiscal_document_service)
):
    """
    Recupera tutti i documenti di reso con paginazione.
    """
    returns = await fiscal_document_service.get_fiscal_documents_by_type('return', page, limit)
    total_count = await fiscal_document_service.get_fiscal_document_count_by_type('return')
    
    return AllReturnsResponseSchema(
        returns=[ReturnResponseSchema.from_orm(return_doc) for return_doc in returns],
        total=total_count,
        page=page,
        limit=limit
    )


# ==================== ENDPOINT PER ORDER DETAIL ====================

@router.post("/{order_id}/order_detail", 
            status_code=status.HTTP_201_CREATED,
            response_model=OrderDetailResponseSchema,
            summary="Aggiungi articolo all'ordine",
            description="Aggiunge un nuovo articolo all'ordine. I totali vengono ricalcolati automaticamente.",
            response_description="Articolo aggiunto con successo")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def add_order_detail(
    order_id: int = Path(..., gt=0, description="ID dell'ordine"),
    order_detail_data: OrderDetailCreateSchema = Body(...),
    user: dict = Depends(get_current_user),
    order_service: IOrderService = Depends(get_order_service),
    product_service: ProductService = Depends(get_product_service),
    order_detail_repo: OrderDetailRepository = Depends(get_order_detail_repository)
):
    """
    Aggiunge un nuovo articolo all'ordine.
    
    **Campi obbligatori:**
    - `id_tax`: ID aliquota IVA
    - `product_name`: Nome prodotto
    - `product_qty`: Quantità
    - `product_weight`: Peso prodotto
    - `unit_price_with_tax`: Prezzo unitario con IVA
    - `total_price_with_tax`: Totale con IVA
    
    **Calcoli automatici:**
    - `unit_price_net` e `total_price_net` vengono calcolati automaticamente da `unit_price_with_tax` e `total_price_with_tax` usando la percentuale IVA di `id_tax`
    
    **Ricalcoli automatici:**
    - `order.total_weight`
    - `order.total_price_net`
    - `order.total_price_with_tax`
    - `order.products_total_price_net`
    - `order.products_total_price_with_tax`
    - `shipping.weight`
    """
    order_detail = await order_service.add_order_detail(order_id, order_detail_data)
    
    # Recupera img_url se id_product è presente
    img_url = None
    if order_detail.id_product:
        images_map = product_service.get_product_images_map([order_detail.id_product])
        img_url = images_map.get(order_detail.id_product)
    
    # Formatta la risposta
    return order_detail_repo.formatted_output(order_detail, img_url=img_url)


@router.put("/{order_id}/order_detail/{id_order_detail}", 
           status_code=status.HTTP_200_OK,
           response_model=OrderDetailResponseSchema,
           summary="Modifica articolo ordine",
           description="Modifica un articolo esistente nell'ordine. Solo i campi forniti vengono aggiornati. I totali vengono ricalcolati automaticamente se necessario.",
           response_description="Articolo aggiornato con successo")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_order_detail(
    order_id: int = Path(..., gt=0, description="ID dell'ordine"),
    id_order_detail: int = Path(..., gt=0, description="ID dell'articolo"),
    order_detail_data: OrderDetailUpdateSchema = Body(...),
    user: dict = Depends(get_current_user),
    order_service: IOrderService = Depends(get_order_service),
    product_service: ProductService = Depends(get_product_service),
    order_detail_repo: OrderDetailRepository = Depends(get_order_detail_repository)
):
    """
    Modifica un articolo esistente nell'ordine.
    
    **Aggiornamenti parziali:**
    - Solo i campi forniti nel JSON vengono aggiornati
    - Tutti i campi sono opzionali
    
    **Ricalcolo automatico:**
    I totali dell'ordine vengono ricalcolati se vengono modificati:
    - `id_tax`, `product_qty`, `product_weight`
    - `unit_price_net`, `unit_price_with_tax`
    - `reduction_percent`, `reduction_amount`
    - `total_price_net`, `total_price_with_tax`
    
    **Calcolo prezzi netti:**
    Se `unit_price_with_tax` o `total_price_with_tax` vengono forniti senza i corrispondenti valori netti,
    questi vengono calcolati automaticamente usando la percentuale IVA di `id_tax`.
    
    **Aggiornamento peso spedizione:**
    Il peso della spedizione viene aggiornato automaticamente se viene modificato `product_weight` o `product_qty`.
    """
    order_detail = await order_service.update_order_detail(order_id, id_order_detail, order_detail_data)
    
    # Recupera img_url se id_product è presente
    img_url = None
    if order_detail.id_product:
        images_map = product_service.get_product_images_map([order_detail.id_product])
        img_url = images_map.get(order_detail.id_product)
    
    # Formatta la risposta
    return order_detail_repo.formatted_output(order_detail, img_url=img_url)


@router.delete("/{order_id}/order_detail/{id_order_detail}", 
              status_code=status.HTTP_200_OK,
              summary="Rimuovi articolo ordine",
              description="Rimuove un articolo dall'ordine. I totali vengono ricalcolati automaticamente.",
              response_description="Articolo rimosso con successo")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
async def remove_order_detail(
    order_id: int = Path(..., gt=0, description="ID dell'ordine"),
    id_order_detail: int = Path(..., gt=0, description="ID dell'articolo"),
    user: dict = Depends(get_current_user),
    order_service: IOrderService = Depends(get_order_service)
):
    """
    Rimuove un articolo dall'ordine.
    
    **Ricalcoli automatici:**
    - `order.total_weight`
    - `order.total_price_net`
    - `order.total_price_with_tax`
    - `order.products_total_price_net`
    - `order.products_total_price_with_tax`
    - `shipping.weight`
    """
    success = await order_service.remove_order_detail(order_id, id_order_detail)
    
    if not success:
        raise HTTPException(status_code=500, detail="Errore durante la rimozione dell'articolo")
    
    return {"message": "Articolo rimosso con successo", "order_id": order_id, "id_order_detail": id_order_detail}
