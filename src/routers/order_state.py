"""
OrderState Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from src.services.interfaces.order_state_service_interface import IOrderStateService
from src.repository.interfaces.order_state_repository_interface import IOrderStateRepository
from src.schemas.order_state_schema import OrderStateSchema, OrderStateResponseSchema, AllOrdersStateResponseSchema
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
    prefix="/api/v1/order_states",
    tags=["OrderState"]
)

def get_order_state_service(db: db_dependency) -> IOrderStateService:
    """Dependency injection per OrderState Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    order_state_repo = configured_container.resolve_with_session(IOrderStateRepository, db)
    
    # Crea il service con il repository
    order_state_service = configured_container.resolve(IOrderStateService)
    # Inietta il repository nel service
    if hasattr(order_state_service, '_order_state_repository'):
        order_state_service._order_state_repository = order_state_repo
    
    return order_state_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllOrdersStateResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_order_states(
    user: dict = Depends(get_current_user),
    order_state_service: IOrderStateService = Depends(get_order_state_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i order_state con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    try:
        order_states = await order_state_service.get_order_states(page=page, limit=limit)
        if not order_states:
            raise HTTPException(status_code=404, detail="Nessun order_state trovato")

        total_count = await order_state_service.get_order_states_count()

        return {"states": order_states, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{order_state_id}", status_code=status.HTTP_200_OK, response_model=OrderStateResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_order_state_by_id(
    user: dict = Depends(get_current_user),
    order_state_service: IOrderStateService = Depends(get_order_state_service),
    order_state_id: int = Path(gt=0)
):
    """
    Restituisce un singolo order_state basato sull'ID specificato.

    - **order_state_id**: Identificativo del order_state da ricercare.
    """
    try:
        order_state = await order_state_service.get_order_state(order_state_id)
        return order_state
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="OrderState non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="OrderState creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_order_state(
    order_state_data: OrderStateSchema,
    order_state_service: IOrderStateService = Depends(get_order_state_service),
    user: dict = Depends(get_current_user)
):
    """
    Crea un nuovo order_state con i dati forniti.
    """
    try:
        return await order_state_service.create_order_state(order_state_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{order_state_id}", status_code=status.HTTP_200_OK, response_description="OrderState aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_order_state(
    order_state_data: OrderStateSchema,
    order_state_service: IOrderStateService = Depends(get_order_state_service),
    order_state_id: int = Path(gt=0),
    user: dict = Depends(get_current_user)
):
    """
    Aggiorna i dati di un order_state esistente basato sull'ID specificato.

    - **order_state_id**: Identificativo del order_state da aggiornare.
    """
    try:
        return await order_state_service.update_order_state(order_state_id, order_state_data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="OrderState non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{order_state_id}", status_code=status.HTTP_200_OK, response_description="OrderState eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_order_state(
    user: dict = Depends(get_current_user),
    order_state_service: IOrderStateService = Depends(get_order_state_service),
    order_state_id: int = Path(gt=0)
):
    """
    Elimina un order_state basato sull'ID specificato.

    - **order_state_id**: Identificativo del order_state da eliminare.
    """
    try:
        await order_state_service.delete_order_state(order_state_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="OrderState non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
