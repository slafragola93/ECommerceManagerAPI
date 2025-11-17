"""
Router per gestione PlatformStateTrigger - Configurazione trigger sincronizzazione stati
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session

from src.database import get_db
from src.services.core.wrap import check_authentication
from src.services.routers.auth_service import authorize, get_current_user
from src.repository.platform_state_trigger_repository import PlatformStateTriggerRepository
from src.schemas.platform_state_trigger_schema import (
    PlatformStateTriggerSchema,
    PlatformStateTriggerUpdateSchema,
    PlatformStateTriggerResponseSchema
)
from src.events.core.event import EventType

router = APIRouter(prefix="/api/v1/platform-state-triggers", tags=["Platform State Triggers"])


def get_repository(db: Session = Depends(get_db)) -> PlatformStateTriggerRepository:
    """Dependency per ottenere repository"""
    return PlatformStateTriggerRepository(db)


@router.get(
    "/",
    response_model=List[PlatformStateTriggerResponseSchema],
    status_code=status.HTTP_200_OK,
    response_description="Lista trigger sincronizzazione stati"
)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_platform_state_triggers(
    page: int = Query(1, ge=1, description="Numero pagina"),
    limit: int = Query(100, ge=1, le=1000, description="Limite risultati per pagina"),
    event_type: Optional[str] = Query(None, description="Filtra per tipo evento"),
    id_platform: Optional[int] = Query(None, gt=0, description="Filtra per ID piattaforma"),
    is_active: Optional[bool] = Query(None, description="Filtra per trigger attivi"),
    user: dict = Depends(get_current_user),
    repo: PlatformStateTriggerRepository = Depends(get_repository)
):
    """
    Ottiene lista di tutti i trigger di sincronizzazione stati.
    
    Filtri disponibili:
    - event_type: Tipo evento (es. order_status_changed)
    - id_platform: ID piattaforma
    - is_active: Solo trigger attivi
    """
    try:
        filters = {"page": page, "limit": limit}
        if event_type:
            filters["event_type"] = event_type
        if id_platform:
            filters["id_platform"] = id_platform
        if is_active is not None:
            filters["is_active"] = is_active
        
        triggers = repo.get_all(**filters)
        return triggers
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore recupero trigger: {str(e)}"
        )


@router.get(
    "/{trigger_id}",
    response_model=PlatformStateTriggerResponseSchema,
    status_code=status.HTTP_200_OK,
    response_description="Trigger sincronizzazione stato"
)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_platform_state_trigger(
    trigger_id: int = Path(gt=0, description="ID trigger"),
    user: dict = Depends(get_current_user),
    repo: PlatformStateTriggerRepository = Depends(get_repository)
):
    """Ottiene un trigger specifico per ID."""
    trigger = repo.get_by_id(trigger_id)
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trigger {trigger_id} non trovato"
        )
    return trigger


@router.post(
    "/",
    response_model=PlatformStateTriggerResponseSchema,
    status_code=status.HTTP_201_CREATED,
    response_description="Trigger creato con successo"
)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_platform_state_trigger(
    trigger_data: PlatformStateTriggerSchema,
    user: dict = Depends(get_current_user),
    repo: PlatformStateTriggerRepository = Depends(get_repository)
):
    """
    Crea un nuovo trigger di sincronizzazione stato.
    
    Esempio:
    ```json
    {
        "event_type": "order_status_changed",
        "id_platform": 1,
        "state_type": "order_state",
        "id_state_local": 2,
        "id_state_platform": 5,
        "is_active": true
    }
    ```
    """
    try:
        from src.models.platform_state_trigger import PlatformStateTrigger
        
        # Valida event_type
        from src.events.core.event import EventType
        valid_events = [e.value for e in EventType]
        if trigger_data.event_type not in valid_events:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"event_type deve essere uno degli eventi validi. Usa GET /api/v1/events/list per vedere la lista completa."
            )
        
        # Valida state_type
        valid_state_types = ['order_state', 'shipping_state']
        if trigger_data.state_type not in valid_state_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"state_type deve essere 'order_state' o 'shipping_state'"
            )
        
        # Crea trigger
        trigger = PlatformStateTrigger(**trigger_data.model_dump())
        created_trigger = repo.create(trigger)
        return created_trigger
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore creazione trigger: {str(e)}"
        )


@router.put(
    "/{trigger_id}",
    response_model=PlatformStateTriggerResponseSchema,
    status_code=status.HTTP_200_OK,
    response_description="Trigger aggiornato con successo"
)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_platform_state_trigger(
    trigger_id: int = Path(gt=0, description="ID trigger"),
    trigger_data: PlatformStateTriggerUpdateSchema = ...,
    user: dict = Depends(get_current_user),
    repo: PlatformStateTriggerRepository = Depends(get_repository)
):
    """Aggiorna un trigger esistente."""
    trigger = repo.get_by_id(trigger_id)
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trigger {trigger_id} non trovato"
        )
    
    try:
        # Aggiorna campi
        for field_name, value in trigger_data.model_dump(exclude_unset=True).items():
            if hasattr(trigger, field_name) and value is not None:
                setattr(trigger, field_name, value)
        
        updated_trigger = repo.update(trigger)
        return updated_trigger
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore aggiornamento trigger: {str(e)}"
        )


@router.delete(
    "/{trigger_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_description="Trigger eliminato con successo"
)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_platform_state_trigger(
    trigger_id: int = Path(gt=0, description="ID trigger"),
    user: dict = Depends(get_current_user),
    repo: PlatformStateTriggerRepository = Depends(get_repository)
):
    """Elimina un trigger."""
    trigger = repo.get_by_id(trigger_id)
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trigger {trigger_id} non trovato"
        )
    
    try:
        repo.delete(trigger_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore eliminazione trigger: {str(e)}"
        )


@router.get(
    "/events/list",
    status_code=status.HTTP_200_OK,
    response_description="Lista eventi disponibili"
)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_available_events(
    user: dict = Depends(get_current_user)
):
    """
    Restituisce lista di tutti gli eventi disponibili nell'applicazione.
    
    Utile per configurare i trigger di sincronizzazione stati.
    """
    events = EventType.get_all_events()
    return {
        "events": events,
        "total": len(events)
    }

