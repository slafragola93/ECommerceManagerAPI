from fastapi import APIRouter, HTTPException, Path, Depends, Query
from starlette import status
from .dependencies import db_dependency, user_dependency, MAX_LIMIT, LIMIT_DEFAULT
from .. import MessageSchema, MessageResponseSchema, AllMessagesResponseSchema, Message, CurrentMessagesResponseSchema
from src.services.wrap import check_authentication
from ..repository.message_repository import MessageRepository
from ..services.auth import authorize

router = APIRouter(
    prefix='/api/v1/message',
    tags=['Message'],
)


def get_repository(db: db_dependency) -> MessageRepository:
    return MessageRepository(db)


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllMessagesResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_all_messages(user: user_dependency,
                           mr: MessageRepository = Depends(get_repository),
                           user_id: int = Query(None, gt=0),
                           page: int = Query(1, gt=0),
                           limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)):
    """
     Recupera tutti i messaggi.

     Parametri:
     - `page`: Pagina corrente per la paginazione.
     - `limit`: Numero di record per pagina.
     """

    messages = mr.get_all(user_id=user_id, page=page, limit=limit)

    if not messages:
        raise HTTPException(status_code=404, detail="Nessun messaggio trovato")

    return {"messages": messages, "total": len(messages), "page": page, "limit": limit}


@router.get("/{message_id}", status_code=status.HTTP_200_OK, response_model=MessageResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_message_by_id(user: user_dependency,
                            mr: MessageRepository = Depends(get_repository),
                            message_id: int = Path(gt=0)):
    """
     Recupera un singolo messaggio per ID.

     Parametri:
     - `message_id`: ID del messaggio da recuperare.
     """

    message = mr.get_by_id(_id=message_id)

    if message is None:
        raise HTTPException(status_code=404, detail="Messaggio non trovato")

    return message


@router.get("/my_messages/", status_code=status.HTTP_200_OK, response_model=CurrentMessagesResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['R'])
async def get_current_messages(user: user_dependency,
                               mr: MessageRepository = Depends(get_repository)):
    """
     Recupera messaggi collegati all'user.
     """

    message = mr.get_by_id_user(_id=user.get("id"), generic=False)

    if message is None:
        raise HTTPException(status_code=404, detail="Nessun Messaggio trovato")

    return {"messages": message, "total": len(message)}


@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Messaggio creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['C'])
async def create_message(user: user_dependency,
                         ms: MessageSchema,
                         relate_to_user: bool = Query(False),
                         mr: MessageRepository = Depends(get_repository)):
    """
    Crea un nuovo messaggio nel sistema.

    Parametri:
    - `ms`: Schema del messaggio da creare.
    """
    if relate_to_user:
        ms.id_user = user.get("id")
    mr.create(data=ms)


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_description="Indirizzo eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['D'])
async def delete_message(user: user_dependency,
                         mr: MessageRepository = Depends(get_repository),
                         message_id: int = Path(gt=0)):
    """
    Elimina un messaggio dal sistema per l'ID specificato.

    Parametri:
    - `message_id`: ID del messaggio da eliminare.
    """
    message = mr.get_by_id(_id=message_id)

    if message is None:
        raise HTTPException(status_code=404, detail="Messaggio non trovato")

    mr.delete(message=message)


@router.put("/{message_id}", status_code=status.HTTP_200_OK, response_description="Messaggio aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN', 'ORDINI', 'FATTURAZIONE', 'PREVENTIVI'], permissions_required=['U'])
async def update_message(user: user_dependency,
                         ms: MessageSchema,
                         mr: MessageRepository = Depends(get_repository),
                         message_id: int = Path(gt=0)):
    """
     Aggiorna un messaggio esistente.

     Parametri:
     - `message_id`: ID del messaggio da aggiornare.
     """
    message = mr.get_by_id(_id=message_id)

    if message is None:
        raise HTTPException(status_code=404, detail="Messaggio non trovato")

    mr.update(edited_message=message, data=ms)
