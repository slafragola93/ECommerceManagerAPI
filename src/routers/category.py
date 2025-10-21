"""
Category Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
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
    tags=["Category"]
)

def get_category_service(db: db_dependency) -> ICategoryService:
    """Dependency injection per Category Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    category_repo = configured_container.resolve_with_session(ICategoryRepository, db)
    
    # Crea il service con il repository
    category_service = configured_container.resolve(ICategoryService)
    # Inietta il repository nel service
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
    try:
        categories = await category_service.get_categories(page=page, limit=limit)
        if not categories:
            raise HTTPException(status_code=404, detail="Nessun category trovato")

        total_count = await category_service.get_categories_count()

        return {"categories": categories, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{category_id}", status_code=status.HTTP_200_OK, response_model=CategoryResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_category_by_id(
    user: dict = Depends(get_current_user),
    category_service: ICategoryService = Depends(get_category_service),
    category_id: int = Path(gt=0)
):
    """
    Restituisce un singolo category basato sull'ID specificato.

    - **category_id**: Identificativo del category da ricercare.
    """
    try:
        category = await category_service.get_category(category_id)
        return category
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Category non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

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
    try:
        return await category_service.create_category(category_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{category_id}", status_code=status.HTTP_200_OK, response_description="Category aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_category(
    category_data: CategorySchema,
    user: dict = Depends(get_current_user),
    category_service: ICategoryService = Depends(get_category_service),
    category_id: int = Path(gt=0)
):
    """
    Aggiorna i dati di un category esistente basato sull'ID specificato.

    - **category_id**: Identificativo del category da aggiornare.
    """
    try:
        return await category_service.update_category(category_id, category_data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Category non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{category_id}", status_code=status.HTTP_200_OK, response_description="Category eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_category(
    user: dict = Depends(get_current_user),
    category_service: ICategoryService = Depends(get_category_service),
    category_id: int = Path(gt=0)
):
    """
    Elimina un category basato sull'ID specificato.

    - **category_id**: Identificativo del category da eliminare.
    """
    try:
        await category_service.delete_category(category_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Category non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
