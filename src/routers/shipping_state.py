from fastapi import APIRouter, Path, HTTPException
from starlette import status
from src.models.shipping_state import ShippingState
from .dependencies import db_dependency, user_dependency
from .. import ShippingStateSchema
from src.services.wrap import check_authentication
from src.services.tool import edit_entity
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/shipping_state',
    tags=['Shipping State'],
)


@router.get("/", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['R'])
async def get_all_shipping_state(user: user_dependency,
                                 db: db_dependency):
    """
        Restituisce un elenco di tutti gli stati di spedizione disponibili.

        Verifica prima l'autenticazione dell'utente. Se l'utente non è autenticato,
        solleva un'eccezione HTTP con stato 401. Altrimenti, restituisce l'elenco completo
        degli stati di spedizione presenti nel database.
    """

    return db.query(ShippingState).all()


@router.get("/{shipping_state_id}", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['R'])
async def get_shipping_state_by_id(user: user_dependency,
                                   db: db_dependency,
                                   shipping_state_id: int = Path(gt=0)):
    """
        Restituisce i dettagli di uno specifico stato di spedizione basato sull'ID fornito.

        Verifica prima l'autenticazione dell'utente. Se l'utente non è autenticato,
        solleva un'eccezione HTTP con stato 401. Se lo stato di spedizione richiesto non esiste,
        solleva un'eccezione HTTP con stato 404. Altrimenti, restituisce i dettagli dello stato
        di spedizione richiesto.

        Parameters:
        - shipping_state_id: L'ID dello stato di spedizione da cercare.
    """

    shipping_state = db.query(ShippingState).filter(ShippingState.id_shipping_state == shipping_state_id).first()

    if shipping_state is None:
        raise HTTPException(status_code=404, detail="Stato Spedizione non trovato")

    return shipping_state


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Stato spedizione creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['C'])
async def create_shipping_state(user: user_dependency,
                                db: db_dependency,
                                ss: ShippingStateSchema):
    """
        Crea un nuovo stato di spedizione nel database.

        Verifica prima l'autenticazione dell'utente. Se l'utente non è autenticato,
        solleva un'eccezione HTTP con stato 401. Dopo la verifica, procede con la creazione
        del nuovo stato di spedizione basandosi sui dati forniti.
    """

    shipping_state = ShippingState(**ss.model_dump())
    db.add(shipping_state)
    db.commit()


@router.put("/{shipping_state_id}", status_code=status.HTTP_204_NO_CONTENT)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI'], permissions_required=['U'])
async def update_shipping_state(user: user_dependency,
                                db: db_dependency,
                                ss: ShippingStateSchema,
                                shipping_state_id: int = Path(gt=0)):
    """
        Aggiorna i dettagli di uno stato di spedizione esistente nel database.

        Verifica prima l'autenticazione dell'utente. Se l'utente non è autenticato,
        solleva un'eccezione HTTP con stato 401. Se lo stato di spedizione non esiste,
        solleva un'eccezione HTTP con stato 404. Dopo la verifica, procede con l'aggiornamento
        dei dati dello stato di spedizione basandosi sui dati forniti.

        Parameters:
        - shipping_state_id: L'ID dello stato di spedizione da aggiornare.
    """

    shipping_state = db.query(ShippingState).filter(ShippingState.id_shipping_state == shipping_state_id).first()

    if shipping_state is None:
        raise HTTPException(status_code=404, detail="Categoria non trovato.")

    edit_entity(shipping_state, ss)

    db.add(shipping_state)
    db.commit()
