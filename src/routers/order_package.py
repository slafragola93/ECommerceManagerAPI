"""
OrderPackage Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from src.services.interfaces.order_package_service_interface import IOrderPackageService
from src.repository.interfaces.order_package_repository_interface import IOrderPackageRepository
from src.schemas.order_package_schema import OrderPackageSchema, OrderPackageResponseSchema, AllOrderPackagesResponseSchema
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
    prefix="/api/v1/order_packages",
    tags=["OrderPackage"]
)

def get_order_package_service(db: db_dependency) -> IOrderPackageService:
    """Dependency injection per OrderPackage Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    order_package_repo = configured_container.resolve_with_session(IOrderPackageRepository, db)
    
    # Crea il service con il repository
    order_package_service = configured_container.resolve(IOrderPackageService)
    # Inietta il repository nel service
    if hasattr(order_package_service, '_order_package_repository'):
        order_package_service._order_package_repository = order_package_repo
    
    return order_package_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllOrderPackagesResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_order_packages(
    user: dict = Depends(get_current_user),
    order_package_service: IOrderPackageService = Depends(get_order_package_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i order_package con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """

    order_packages = await order_package_service.get_order_packages(page=page, limit=limit)
    if not order_packages:
        raise HTTPException(status_code=404, detail="Nessun order_package trovato")

    total_count = await order_package_service.get_order_packages_count()

    return {"order_packages": order_packages, "total": total_count, "page": page, "limit": limit}

@router.get("/{order_package_id}", status_code=status.HTTP_200_OK, response_model=OrderPackageResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_order_package_by_id(
    user: dict = Depends(get_current_user),
    order_package_service: IOrderPackageService = Depends(get_order_package_service),
    order_package_id: int = Path(gt=0)
):
    """
    Restituisce un singolo order_package basato sull'ID specificato.

    - **order_package_id**: Identificativo del order_package da ricercare.
    """
    return await order_package_service.get_order_package(order_package_id)

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="OrderPackage creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_order_package(
    order_package_data: OrderPackageSchema,
    order_package_service: IOrderPackageService = Depends(get_order_package_service),
    user: dict = Depends(get_current_user)
):
    """
    Crea un nuovo order_package con i dati forniti.
    """
    return await order_package_service.create_order_package(order_package_data)

@router.put("/{order_package_id}", status_code=status.HTTP_200_OK, response_description="OrderPackage aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_order_package(
    order_package_data: OrderPackageSchema,
    order_package_service: IOrderPackageService = Depends(get_order_package_service),
    order_package_id: int = Path(gt=0),
    user: dict = Depends(get_current_user)
):
    """
    Aggiorna i dati di un order_package esistente basato sull'ID specificato.

    - **order_package_id**: Identificativo del order_package da aggiornare.
    """
    return await order_package_service.update_order_package(order_package_id, order_package_data)

@router.delete("/{order_package_id}", status_code=status.HTTP_200_OK, response_description="OrderPackage eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_order_package(
    user: dict = Depends(get_current_user),
    order_package_service: IOrderPackageService = Depends(get_order_package_service),
    order_package_id: int = Path(gt=0)
):
    """
    Elimina un order_package basato sull'ID specificato.

    - **order_package_id**: Identificativo del order_package da eliminare.
    """
    await order_package_service.delete_order_package(order_package_id)