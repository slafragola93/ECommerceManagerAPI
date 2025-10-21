"""
Category Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Path, UploadFile, File, Form
from src.services.interfaces.category_service_interface import ICategoryService
from src.repository.interfaces.category_repository_interface import ICategoryRepository
from src.schemas.category_schema import CategorySchema, CategoryResponseSchema, AllCategoryResponseSchema
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
    prefix="/api/v1/categories",
    tags=["Category"],
)

def get_category_service(db: db_dependency) -> ICategoryService:
    """Dependency injection per Category Service"""
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    category_repo = configured_container.resolve_with_session(ICategoryRepository, db)
    category_service = configured_container.resolve(ICategoryService)
    
    if hasattr(category_service, '_category_repository'):
        category_service._category_repository = category_repo
    
    return category_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllCategoryResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_categories(
    user: dict = Depends(get_current_user),
    category_service: ICategoryService = Depends(get_category_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i category con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    categories = await category_service.get_categories(page=page, limit=limit)
    if not categories:
        raise NotFoundException("Categories", None)

    total_count = await category_service.get_categories_count()

    return {"categories": categories, "total": total_count, "page": page, "limit": limit}

@router.get("/{category_id}", status_code=status.HTTP_200_OK, response_model=CategoryResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_category_by_id(
    category_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    category_service: ICategoryService = Depends(get_category_service)
):
    """
    Restituisce un singolo category basato sull'ID specificato.

    - **category_id**: Identificativo del category da ricercare.
    """
    category = await category_service.get_category(category_id)
    return category

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Category creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_category(
    category_data: CategorySchema,
    user: dict = Depends(get_current_user),
    category_service: ICategoryService = Depends(get_category_service)
):
    """
    Crea un nuovo category con i dati forniti.
    """
    return await category_service.create_category(category_data)

@router.put("/{category_id}", status_code=status.HTTP_200_OK, response_description="Category aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_category(
    category_data: CategorySchema,
    category_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    category_service: ICategoryService = Depends(get_category_service)
):
    """
    Aggiorna i dati di un category esistente basato sull'ID specificato.

    - **category_id**: Identificativo del category da aggiornare.
    """
    return await category_service.update_category(category_id, category_data)

@router.delete("/{category_id}", status_code=status.HTTP_200_OK, response_description="Category eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_category(
    category_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    category_service: ICategoryService = Depends(get_category_service)
):
    """
    Elimina un category basato sull'ID specificato.

    - **category_id**: Identificativo del category da eliminare.
    """
    await category_service.delete_category(category_id)