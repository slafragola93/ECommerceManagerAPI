"""
Product Router rifattorizzato seguendo i principi SOLID
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, UploadFile, File, Form
from typing import Optional
from src.services.interfaces.product_service_interface import IProductService
from src.repository.interfaces.product_repository_interface import IProductRepository
from src.repository.interfaces.platform_repository_interface import IPlatformRepository
from src.schemas.product_schema import ProductSchema, ProductResponseSchema, AllProductsResponseSchema
from src.core.exceptions import (
    NotFoundException
)
from src.core.dependencies import db_dependency
from src.services.routers.auth_service import authorize
from src.services.core.wrap import check_authentication
from src.services.media.image_service import ImageService
from .dependencies import LIMIT_DEFAULT, MAX_LIMIT
from src.services.routers.auth_service import get_current_user
from src.database import get_db

router = APIRouter(
    prefix="/api/v1/products",
    tags=["Product"]
)

def get_product_service(db: db_dependency) -> IProductService:
    """Dependency injection per Product Service"""
    from src.core.container_config import get_configured_container

    configured_container = get_configured_container()

    product_repo = configured_container.resolve_with_session(IProductRepository, db)
    platform_repo = configured_container.resolve_with_session(IPlatformRepository, db)

    product_service = configured_container.resolve(IProductService)

    if hasattr(product_service, "set_dependencies"):
        product_service.set_dependencies(product_repo, platform_repo, db)
    elif hasattr(product_service, "_product_repository"):
        product_service._product_repository = product_repo

    return product_service


@router.get("/", status_code=status.HTTP_200_OK, response_model=AllProductsResponseSchema)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_all_products(
    user: dict = Depends(get_current_user),
    product_service: IProductService = Depends(get_product_service),
    page: int = Query(1, gt=0),
    limit: int = Query(LIMIT_DEFAULT, gt=0, le=MAX_LIMIT),
    product_name: Optional[str] = Query(None, description="Filtra prodotti per nome (ricerca parziale)")
):
    """
    Restituisce tutti i product con supporto alla paginazione e filtro per nome.
    
    - **page**: La pagina da restituire, per la paginazione dei risultati.
    - **limit**: Il numero massimo di risultati per pagina.
    - **product_name**: Filtra i prodotti che contengono questa stringa in name, sku o reference (minimo 4 caratteri, ricerca parziale, case-insensitive).
    """
    filters = {}
    if product_name and len(product_name.strip()) >= 4:
        filters['product_name'] = product_name.strip()
    
    products = await product_service.get_products(page=page, limit=limit, **filters)
    if not products:
        raise NotFoundException("Products", None)

    total_count = await product_service.get_products_count(**filters)

    return {"products": products, "total": total_count, "page": page, "limit": limit}

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
    return await product_service.get_product(product_id)

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
    return await product_service.create_product(product_data)

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
    return await product_service.update_product(product_id, product_data)

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
    await product_service.delete_product(product_id)


@router.post("/{product_id}/upload-image", status_code=status.HTTP_200_OK, response_description="Immagine caricata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def upload_product_image(
    product_id: int = Path(gt=0),
    file: UploadFile = File(...),
    platform_id: int = Form(1),
    user: dict = Depends(get_current_user),
    product_service: IProductService = Depends(get_product_service)
):
    """
    Carica un'immagine per un prodotto specifico.
    
    - **product_id**: ID del prodotto
    - **file**: File immagine da caricare
    - **platform_id**: ID della piattaforma (default: 1)
    """
    # Verifica che il prodotto esista
    product = await product_service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product non trovato")
    
    # Verifica il tipo di file
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Il file deve essere un'immagine")
    
    # Verifica la dimensione del file (max 10MB)
    file_content = await file.read()
    if len(file_content) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=400, detail="Il file è troppo grande (max 10MB)")
    
    # Salva l'immagine
    image_service = ImageService()
    img_url = await image_service.save_uploaded_image(
        file_content, 
        product_id, 
        platform_id, 
        file.filename
    )
    
    # Aggiorna il prodotto con l'URL dell'immagine
    from src.schemas.product_schema import ProductUpdateSchema
    update_data = ProductUpdateSchema(img_url=img_url)
    await product_service.update_product(product_id, update_data)
    
    return {
        "message": "Immagine caricata con successo",
        "product_id": product_id,
        "img_url": img_url,
        "filename": file.filename
    }


@router.delete("/{product_id}/image", status_code=status.HTTP_200_OK, response_description="Immagine eliminata correttamente")
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['U'])
async def delete_product_image(
    product_id: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    product_service: IProductService = Depends(get_product_service)
):
    """
    Elimina l'immagine di un prodotto.
    
    - **product_id**: ID del prodotto
    """

    # Recupera il prodotto
    product = await product_service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product non trovato")
    
    if not product.img_url:
        raise HTTPException(status_code=404, detail="Il prodotto non ha un'immagine")
    
    # Elimina il file dal filesystem
    image_service = ImageService()
    deleted = image_service.delete_image(product.img_url)
    
    if deleted:
        # Aggiorna il prodotto rimuovendo l'URL dell'immagine
        from src.schemas.product_schema import ProductUpdateSchema
        update_data = ProductUpdateSchema(img_url=None)
        await product_service.update_product(product_id, update_data)
        
        return {
            "message": "Immagine eliminata con successo",
            "product_id": product_id
        }
    else:
        raise HTTPException(status_code=500, detail="Errore durante l'eliminazione del file")


@router.get("/get-live-price/{id_origin}", status_code=status.HTTP_200_OK)
@check_authentication
@authorize(roles_permitted=['ADMIN'], permissions_required=['R'])
async def get_live_price(
    id_origin: int = Path(gt=0),
    user: dict = Depends(get_current_user),
    product_service: IProductService = Depends(get_product_service)
):
    """Recupera il prezzo live di un prodotto demandando la logica al service applicativo."""

    price = await product_service.get_live_price(id_origin)

    return {"ecommerce_price": price}