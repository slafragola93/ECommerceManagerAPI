"""
ShippingState Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from src.services.interfaces.shipping_state_service_interface import IShippingStateService
from src.repository.interfaces.shipping_state_repository_interface import IShippingStateRepository
from src.schemas.shipping_state_schema import ShippingStateSchema, ShippingStateResponseSchema, AllShippingStatesResponseSchema
from src.core.container import container
from src.core.exceptions import (
    BaseApplicationException,
    ValidationException,
    NotFoundException,
    BusinessRuleException
)
from src.core.dependencies import db_dependency
from src.services.auth import authorize
from src.services.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/shipping_states",
    tags=["ShippingState"]
)

def get_shipping_state_service(db: db_dependency) -> IShippingStateService:
    """Dependency injection per ShippingState Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    shipping_state_repo = configured_container.resolve_with_session(IShippingStateRepository, db)
    
    # Crea il service con il repository
    shipping_state_service = configured_container.resolve(IShippingStateService)
    # Inietta il repository nel service
    if hasattr(shipping_state_service, '_shipping_state_repository'):
        shipping_state_service._shipping_state_repository = shipping_state_repo
    
    return shipping_state_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllShippingStatesResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_shipping_states(
    user: dict = Depends(get_current_user),
    shipping_state_service: IShippingStateService = Depends(get_shipping_state_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i shipping_state con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    try:
        shipping_states = await shipping_state_service.get_shipping_states(page=page, limit=limit)
        if not shipping_states:
            raise HTTPException(status_code=404, detail="Nessun shipping_state trovato")

        total_count = await shipping_state_service.get_shipping_states_count()

        return {"shipping_states": shipping_states, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{shipping_state_id}", status_code=status.HTTP_200_OK, response_model=ShippingStateResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_shipping_state_by_id(
    user: dict = Depends(get_current_user),
    shipping_state_service: IShippingStateService = Depends(get_shipping_state_service),
    shipping_state_id: int = Path(gt=0)
):
    """
    Restituisce un singolo shipping_state basato sull'ID specificato.

    - **shipping_state_id**: Identificativo del shipping_state da ricercare.
    """
    try:
        shipping_state = await shipping_state_service.get_shipping_state(shipping_state_id)
        return shipping_state
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="ShippingState non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="ShippingState creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_shipping_state(
    shipping_state_data: ShippingStateSchema,
    user: dict = Depends(get_current_user),
    shipping_state_service: IShippingStateService = Depends(get_shipping_state_service)
):
    """
    Crea un nuovo shipping_state con i dati forniti.
    """
    try:
        return await shipping_state_service.create_shipping_state(shipping_state_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{shipping_state_id}", status_code=status.HTTP_200_OK, response_description="ShippingState aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_shipping_state(
    shipping_state_data: ShippingStateSchema,
    user: dict = Depends(get_current_user),
    shipping_state_service: IShippingStateService = Depends(get_shipping_state_service),
    shipping_state_id: int = Path(gt=0)
):
    """
    Aggiorna i dati di un shipping_state esistente basato sull'ID specificato.

    - **shipping_state_id**: Identificativo del shipping_state da aggiornare.
    """
    try:
        return await shipping_state_service.update_shipping_state(shipping_state_id, shipping_state_data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="ShippingState non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{shipping_state_id}", status_code=status.HTTP_200_OK, response_description="ShippingState eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_shipping_state(
    user: dict = Depends(get_current_user),
    shipping_state_service: IShippingStateService = Depends(get_shipping_state_service),
    shipping_state_id: int = Path(gt=0)
):
    """
    Elimina un shipping_state basato sull'ID specificato.

    - **shipping_state_id**: Identificativo del shipping_state da eliminare.
    """
    try:
        await shipping_state_service.delete_shipping_state(shipping_state_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="ShippingState non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
