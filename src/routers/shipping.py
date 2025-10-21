"""
Shipping Router rifattorizzato seguendo i principi SOLID
"""
from fastapi import APIRouter, Depends, status, Query, Path
from src.services.interfaces.shipping_service_interface import IShippingService
from src.repository.interfaces.shipping_repository_interface import IShippingRepository
from src.schemas.shipping_schema import ShippingSchema, ShippingResponseSchema, AllShippingResponseSchema
from src.core.container import container
from src.core.exceptions import (
    NotFoundException
)
from src.core.dependencies import db_dependency
from src.services.routers.auth_service import authorize
from src.services.core.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.routers.auth_service import get_current_user

router = APIRouter(
    prefix="/api/v1/shippings",
    tags=["Shipping"],
)

def get_shipping_service(db: db_dependency) -> IShippingService:
    """Dependency injection per Shipping Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    shipping_repo = configured_container.resolve_with_session(IShippingRepository, db)
    shipping_service = configured_container.resolve(IShippingService)
    
    if hasattr(shipping_service, '_shipping_repository'):
        shipping_service._shipping_repository = shipping_repo
    
    return shipping_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllShippingResponseSchema)
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
    shippings = await shipping_service.get_shippings(page=page, limit=limit)
    if not shippings:
        raise NotFoundException("Shippings", None)

    total_count = await shipping_service.get_shippings_count()

    return {"shippings": shippings, "total": total_count, "page": page, "limit": limit}

@router.get("/{shipping_id}", status_code=status.HTTP_200_OK, response_model=ShippingResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_shipping_by_id(
    shipping_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    shipping_service: IShippingService = Depends(get_shipping_service)
):
    """
    Restituisce un singolo shipping basato sull'ID specificato.

    - **shipping_id**: Identificativo del shipping da ricercare.
    """
    shipping = await shipping_service.get_shipping(shipping_id)
    return shipping

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Spedizione creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_shipping(
    shipping_data: ShippingSchema,
    user: dict = Depends(get_current_user),
    shipping_service: IShippingService = Depends(get_shipping_service)
):
    """
    Crea un nuovo shipping con i dati forniti.
    """
    return await shipping_service.create_shipping(shipping_data)

@router.put("/{shipping_id}", status_code=status.HTTP_200_OK, response_description="Spedizione aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_shipping(
    shipping_data: ShippingSchema,
    shipping_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    shipping_service: IShippingService = Depends(get_shipping_service)
):
    """
    Aggiorna i dati di un shipping esistente basato sull'ID specificato.

    - **shipping_id**: Identificativo del shipping da aggiornare.
    """
    return await shipping_service.update_shipping(shipping_id, shipping_data)

@router.delete("/{shipping_id}", status_code=status.HTTP_200_OK, response_description="Spedizione eliminata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_shipping(
    shipping_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    shipping_service: IShippingService = Depends(get_shipping_service)
):
    """
    Elimina un shipping basato sull'ID specificato.

    - **shipping_id**: Identificativo del shipping da eliminare.
    """
    await shipping_service.delete_shipping(shipping_id)