"""
Brand Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
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
from src.services.auth import authorize
from src.services.wrap import check_authentication
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/brands",
    tags=["Brand"]
)

def get_brand_service(db: db_dependency) -> IBrandService:
    """Dependency injection per Brand Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    brand_repo = configured_container.resolve_with_session(IBrandRepository, db)
    
    # Crea il service con il repository
    brand_service = configured_container.resolve(IBrandService)
    # Inietta il repository nel service
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
    try:
        brands = await brand_service.get_brands(page=page, limit=limit)
        if not brands:
            raise HTTPException(status_code=404, detail="Nessun brand trovato")

        total_count = await brand_service.get_brands_count()

        return {"brands": brands, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{brand_id}", status_code=status.HTTP_200_OK, response_model=BrandResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_brand_by_id(
    user: dict = Depends(get_current_user),
    brand_service: IBrandService = Depends(get_brand_service),
    brand_id: int = Path(gt=0)
):
    """
    Restituisce un singolo brand basato sull'ID specificato.

    - **brand_id**: Identificativo del brand da ricercare.
    """
    try:
        brand = await brand_service.get_brand(brand_id)
        return brand
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Brand non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

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
    try:
        return await brand_service.create_brand(brand_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

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
    try:
        return await brand_service.update_brand(brand_id, brand_data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Brand non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{brand_id}", status_code=status.HTTP_200_OK, response_description="Brand eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_brand(
    user: dict = Depends(get_current_user),
    brand_service: IBrandService = Depends(get_brand_service),
    brand_id: int = Path(gt=0)
):
    """
    Elimina un brand basato sull'ID specificato.

    - **brand_id**: Identificativo del brand da eliminare.
    """
    try:
        await brand_service.delete_brand(brand_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Brand non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
