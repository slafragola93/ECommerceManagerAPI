from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from starlette import status
from .dependencies import db_dependency, user_dependency, MAX_LIMIT, LIMIT_DEFAULT
from .. import OrderSchema
from ..schemas.order_schema import OrderResponseSchema, AllOrderResponseSchema, OrderIdSchema, OrderUpdateSchema
from src.services.wrap import check_authentication
from ..repository.order_repository import OrderRepository
from ..services.auth import authorize
from ..models.relations.relations import orders_history

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
    Recupera un singolo ordine per ID.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `order_id`: ID dell'ordine da recuperare.
    """
    order = or_repo.get_by_id(_id=order_id)

    if order is None:
        raise HTTPException(status_code=404, detail="Ordine non trovato")

    return or_repo.formatted_output(order)


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
    
    # Aggiungi record nell'order history
    order_history_insert = orders_history.insert().values(
        id_order=order_id,
        id_order_state=new_status_id
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


@router.get("/{order_id}/details", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_order_details(user: user_dependency,
                           or_repo: OrderRepository = Depends(get_repository),
                           order_id: int = Path(gt=0)):
    """
    Recupera i dettagli di un ordine (prodotti, quantità, prezzi).

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `order_id`: ID dell'ordine.
    """
    order = or_repo.get_by_id(_id=order_id)

    if order is None:
        raise HTTPException(status_code=404, detail="Ordine non trovato")

    # Recupera i dettagli dell'ordine
    order_details = or_repo.order_detail_repository.get_by_id_order(order_id)
    
    return {
        "order_id": order_id,
        "order_details": [or_repo.order_detail_repository.formatted_output(detail) for detail in order_details] if order_details else []
    }


@router.get("/{order_id}/summary", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'USER', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_order_summary(user: user_dependency,
                           or_repo: OrderRepository = Depends(get_repository),
                           order_id: int = Path(gt=0)):
    """
    Recupera un riassunto completo di un ordine con tutte le informazioni correlate.

    Parametri:
    - `user`: Dipendenza dell'utente autenticato.
    - `order_id`: ID dell'ordine.
    """
    order = or_repo.get_by_id(_id=order_id)

    if order is None:
        raise HTTPException(status_code=404, detail="Ordine non trovato")

    # Recupera informazioni correlate
    order_details = or_repo.order_detail_repository.get_by_id_order(order_id)
    # order_packages = or_repo.order_package_repository.get_by_order_id(order_id)  # Da implementare se necessario
    
    return {
        "order": or_repo.formatted_output(order),
        "order_details": [or_repo.order_detail_repository.formatted_output(detail) for detail in order_details] if order_details else [],
        "order_packages": [],  #TODO: Da implementare quando sarà disponibile il metodo
        "summary": {
            "total_items": len(order_details) if order_details else 0,
            "total_packages": 0,  #TODO: Da implementare quando sarà disponibile
            "total_weight": order.total_weight or 0,
            "total_price": order.total_price or 0
        }
    }

