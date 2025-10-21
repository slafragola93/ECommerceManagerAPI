"""
Brand Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Path, UploadFile, File, Form
from src.services.interfaces.brand_service_interface import IBrandService
from src.repository.interfaces.brand_repository_interface import IBrandRepository
from src.schemas.brand_schema import BrandSchema, BrandResponseSchema, AllBrandsResponseSchema
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
    prefix="/api/v1/brands",
    tags=["Brand"],
)

def get_brand_service(db: db_dependency) -> IBrandService:
    """Dependency injection per Brand Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    brand_repo = configured_container.resolve_with_session(IBrandRepository, db)
    brand_service = configured_container.resolve(IBrandService)
    
    if hasattr(brand_service, '_brand_repository'):
        brand_service._brand_repository = brand_repo
    
    return brand_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllBrandsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_brands(
    user: dict = Depends(get_current_user),
    brand_service: IBrandService = Depends(get_brand_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i brand con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    brands = await brand_service.get_brands(page=page, limit=limit)
    if not brands:
        raise NotFoundException("Brands", None)

    total_count = await brand_service.get_brands_count()

    return {"brands": brands, "total": total_count, "page": page, "limit": limit}

@router.get("/{brand_id}", status_code=status.HTTP_200_OK, response_model=BrandResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_brand_by_id(
    brand_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    brand_service: IBrandService = Depends(get_brand_service)
):
    """
    Restituisce un singolo brand basato sull'ID specificato.

    - **brand_id**: Identificativo del brand da ricercare.
    """
    brand = await brand_service.get_brand(brand_id)
    return brand

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Brand creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_brand(
    brand_data: BrandSchema,
    user: dict = Depends(get_current_user),
    brand_service: IBrandService = Depends(get_brand_service)
):
    """
    Crea un nuovo brand con i dati forniti.
    """
    return await brand_service.create_brand(brand_data)

@router.put("/{brand_id}", status_code=status.HTTP_200_OK, response_description="Brand aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_brand(
    brand_data: BrandSchema,
    brand_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    brand_service: IBrandService = Depends(get_brand_service)
):
    """
    Aggiorna i dati di un brand esistente basato sull'ID specificato.

    - **brand_id**: Identificativo del brand da aggiornare.
    """
    return await brand_service.update_brand(brand_id, brand_data)

@router.delete("/{brand_id}", status_code=status.HTTP_200_OK, response_description="Brand eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_brand(
    brand_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    brand_service: IBrandService = Depends(get_brand_service)
):
    """
    Elimina un brand basato sull'ID specificato.

    - **brand_id**: Identificativo del brand da eliminare.
    """
    await brand_service.delete_brand(brand_id)