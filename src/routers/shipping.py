"""
Shipping Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from src.services.interfaces.shipping_service_interface import IShippingService
from src.repository.interfaces.shipping_repository_interface import IShippingRepository
from src.schemas.shipping_schema import ShippingSchema, ShippingResponseSchema, ShippingResponseSchema
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
    prefix="/api/v1/shippings",
    tags=["Shipping"]
)

def get_shipping_service(db: db_dependency) -> IShippingService:
    """Dependency injection per Shipping Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    shipping_repo = configured_container.resolve_with_session(IShippingRepository, db)
    
    # Crea il service con il repository
    shipping_service = configured_container.resolve(IShippingService)
    # Inietta il repository nel service
    if hasattr(shipping_service, '_shipping_repository'):
        shipping_service._shipping_repository = shipping_repo
    
    return shipping_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=ShippingResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_shippings(
    user: dict = Depends(get_current_user),
    shipping_service: IShippingService = Depends(get_shipping_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i shipping con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    try:
        shippings = await shipping_service.get_shippings(page=page, limit=limit)
        if not shippings:
            raise HTTPException(status_code=404, detail="Nessun shipping trovato")

        total_count = await shipping_service.get_shippings_count()

        return {"shippings": shippings, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{shipping_id}", status_code=status.HTTP_200_OK, response_model=ShippingResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_shipping_by_id(
    user: dict = Depends(get_current_user),
    shipping_service: IShippingService = Depends(get_shipping_service),
    shipping_id: int = Path(gt=0)
):
    """
    Restituisce un singolo shipping basato sull'ID specificato.

    - **shipping_id**: Identificativo del shipping da ricercare.
    """
    try:
        shipping = await shipping_service.get_shipping(shipping_id)
        return shipping
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Shipping non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Shipping creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_shipping(
    shipping_data: ShippingSchema,
    shipping_service: IShippingService = Depends(get_shipping_service),
    user: dict = Depends(get_current_user)
):
    """
    Crea un nuovo shipping con i dati forniti.
    """
    try:
        return await shipping_service.create_shipping(shipping_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{shipping_id}", status_code=status.HTTP_200_OK, response_description="Shipping aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_shipping(
    shipping_data: ShippingSchema,
    shipping_service: IShippingService = Depends(get_shipping_service),
    shipping_id: int = Path(gt=0),
    user: dict = Depends(get_current_user)
):
    """
    Aggiorna i dati di un shipping esistente basato sull'ID specificato.

    - **shipping_id**: Identificativo del shipping da aggiornare.
    """
    try:
        return await shipping_service.update_shipping(shipping_id, shipping_data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Shipping non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{shipping_id}", status_code=status.HTTP_200_OK, response_description="Shipping eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_shipping(
    user: dict = Depends(get_current_user),
    shipping_service: IShippingService = Depends(get_shipping_service),
    shipping_id: int = Path(gt=0)
):
    """
    Elimina un shipping basato sull'ID specificato.

    - **shipping_id**: Identificativo del shipping da eliminare.
    """
    try:
        await shipping_service.delete_shipping(shipping_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Shipping non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
