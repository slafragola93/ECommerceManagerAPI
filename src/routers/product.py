"""
Product Router rifattorizzato seguendo i principi SOLID
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from src.services.interfaces.product_service_interface import IProductService
from src.repository.interfaces.product_repository_interface import IProductRepository
from src.schemas.product_schema import ProductSchema, ProductResponseSchema, AllProductsResponseSchema
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
    prefix="/api/v1/products",
    tags=["Product"]
)

def get_product_service(db: db_dependency) -> IProductService:
    """Dependency injection per Product Service"""
    # Configura il container se necessario
    from src.core.container_config import get_configured_container
    configured_container = get_configured_container()
    
    # Crea il repository con la sessione DB usando il metodo specifico
    product_repo = configured_container.resolve_with_session(IProductRepository, db)
    
    # Crea il service con il repository
    product_service = configured_container.resolve(IProductService)
    # Inietta il repository nel service
    if hasattr(product_service, '_product_repository'):
        product_service._product_repository = product_repo
    
    return product_service

@router.get("/", status_code=status.HTTP_200_OK, response_model=AllProductsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_products(
    user: dict = Depends(get_current_user),
    product_service: IProductService = Depends(get_product_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT)
):
    """
    Restituisce tutti i product con supporto alla paginazione.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    """
    try:
        products = await product_service.get_products(page=page, limit=limit)
        if not products:
            raise HTTPException(status_code=404, detail="Nessun product trovato")

        total_count = await product_service.get_products_count()

        return {"products": products, "total": total_count, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{product_id}", status_code=status.HTTP_200_OK, response_model=ProductResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_product_by_id(
    user: dict = Depends(get_current_user),
    product_service: IProductService = Depends(get_product_service),
    product_id: int = Path(gt=0)
):
    """
    Restituisce un singolo product basato sull'ID specificato.

    - **product_id**: Identificativo del product da ricercare.
    """
    try:
        product = await product_service.get_product(product_id)
        return product
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Product non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/", status_code=status.HTTP_201_CREATED, response_description="Product creato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['C'])
async def create_product(
    product_data: ProductSchema,
    user: dict = Depends(get_current_user),
    product_service: IProductService = Depends(get_product_service)
):
    """
    Crea un nuovo product con i dati forniti.
    """
    try:
        return await product_service.create_product(product_data)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{product_id}", status_code=status.HTTP_200_OK, response_description="Product aggiornato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def update_product(
    product_data: ProductSchema,
    user: dict = Depends(get_current_user),
    product_service: IProductService = Depends(get_product_service),
    product_id: int = Path(gt=0)
):
    """
    Aggiorna i dati di un product esistente basato sull'ID specificato.

    - **product_id**: Identificativo del product da aggiornare.
    """
    try:
        return await product_service.update_product(product_id, product_data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Product non trovato")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{product_id}", status_code=status.HTTP_200_OK, response_description="Product eliminato correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['D'])
async def delete_product(
    user: dict = Depends(get_current_user),
    product_service: IProductService = Depends(get_product_service),
    product_id: int = Path(gt=0)
):
    """
    Elimina un product basato sull'ID specificato.

    - **product_id**: Identificativo del product da eliminare.
    """
    try:
        await product_service.delete_product(product_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail="Product non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
