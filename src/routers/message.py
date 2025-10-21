"""
Message Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from src.services.interfaces.message_service_interface import IMessageService
from src.repository.interfaces.message_repository_interface import IMessageRepository
from src.schemas.message_schema import MessageSchema, MessageResponseSchema, AllMessagesResponseSchema
from src.core.container import container
from src.core.exceptions import (
    BaseApplicationException,
    ValidationException,
    NotFoundException,
    BusinessRuleException
)
from src.core.dependencies import db_dependency
from src.services.routers.auth_service import authorize
from src.services.core.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.routers.auth_service import get_current_user

router = APIRouter(
    prefix="/api/v1/messages",
    tags=["Message"]
)

def get_message_service(db: db_dependency) -> IMessageService:
    """Dependency injection per Message Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    message_repo = configured_container.resolve_with_session(IMessageRepository, db)
    
    # Crea il service con il repository
    message_service = configured_container.resolve(IMessageService)
    # Inietta il repository nel service
    if hasattr(message_service, '_message_repository'):
        message_service._message_repository = message_repo
    
    return message_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllMessagesResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_messages(
    user: dict = Depends(get_current_user),
    message_service: IMessageService = Depends(get_message_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i message con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    try:
        messages = await message_service.get_messages(page=page, limit=limit)
        if not messages:
            raise HTTPException(status_code=404, detail="Nessun message trovato")

        total_count = await message_service.get_messages_count()

        return {"messages": messages, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{message_id}", status_code=status.HTTP_200_OK, response_model=MessageResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_message_by_id(
    user: dict = Depends(get_current_user),
    message_service: IMessageService = Depends(get_message_service),
    message_id: int = Path(gt=0)
):
    """
    Restituisce un singolo message basato sull'ID specificato.

    - **message_id**: Identificativo del message da ricercare.
    """
    try:
        message = await message_service.get_message(message_id)
        return message
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Message non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Message creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_message(
    message_data: MessageSchema,
    user: dict = Depends(get_current_user),
    message_service: IMessageService = Depends(get_message_service)
):
    """
    Crea un nuovo message con i dati forniti.
    """
    try:
        return await message_service.create_message(message_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{message_id}", status_code=status.HTTP_200_OK, response_description="Message aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_message(
    message_data: MessageSchema,
    user: dict = Depends(get_current_user),
    message_service: IMessageService = Depends(get_message_service),
    message_id: int = Path(gt=0)
):
    """
    Aggiorna i dati di un message esistente basato sull'ID specificato.

    - **message_id**: Identificativo del message da aggiornare.
    """
    try:
        return await message_service.update_message(message_id, message_data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Message non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{message_id}", status_code=status.HTTP_200_OK, response_description="Message eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_message(
    user: dict = Depends(get_current_user),
    message_service: IMessageService = Depends(get_message_service),
    message_id: int = Path(gt=0)
):
    """
    Elimina un message basato sull'ID specificato.

    - **message_id**: Identificativo del message da eliminare.
    """
    try:
        await message_service.delete_message(message_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Message non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
