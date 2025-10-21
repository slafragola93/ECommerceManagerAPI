"""
Router per la gestione delle immagini statiche con caching
"""

from fastapi import APIRouter, HTTPException, status, Path as FastAPIPath, Query
from fastapi.responses import FileResponse, Response
from pathlib import Path
import os
from typing import Optional
from src.services.media.image_cache_service import get_image_cache_service
from src.core.cached import cached
from src.core.settings import TTL_PRESETS

router = APIRouter(
    prefix="/api/v1/images",
    tags=["Images"]
)


@router.get("/product/{platform_id}/{filename}")
@cached(
    ttl=TTL_PRESETS["product"],  # 6 ore
    key="image_file:{platform_id}:{filename}",
    layer="hybrid"
)
async def get_product_image(
    platform_id: int = FastAPIPath(gt=0),
    filename: str = FastAPIPath(...),
    use_cache: bool = Query(default=True, description="Usa la cache per i metadati")
):
    """
    Serve un'immagine di prodotto con caching intelligente.
    
    - **platform_id**: ID della piattaforma
    - **filename**: Nome del file immagine
    - **use_cache**: Se usare la cache per i metadati
    """
    try:
        # Estrai product_id dal filename (formato: product_123.jpg)
        if not filename.startswith("product_") or not filename.endswith(".jpg"):
            raise HTTPException(status_code=400, detail="Formato filename non valido")
        
        product_id_str = filename.replace("product_", "").replace(".jpg", "")
        try:
            product_id = int(product_id_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="ID prodotto non valido")
        
        # Usa il servizio di cache se abilitato
        if use_cache:
            cache_service = await get_image_cache_service()
            metadata = await cache_service.get_image_metadata(platform_id, product_id)
            
            if metadata and metadata["exists"]:
                return FileResponse(
                    path=metadata["path"],
                    media_type="image/jpeg",
                    filename=filename
                )
        
        # Fallback: controllo diretto del filesystem
        image_path = Path("media/product_images") / str(platform_id) / filename
        fallback_path = Path("media/product_images/fallback/product_not_found.jpg")
        
        # Verifica che il file esista
        if not image_path.exists():
            if fallback_path.exists():
                return FileResponse(
                    path=str(fallback_path),
                    media_type="image/jpeg",
                    filename="product_not_found.jpg"
                )
            raise HTTPException(status_code=404, detail="Immagine non trovata")
        
        # Verifica che sia un file (non una directory)
        if not image_path.is_file():
            raise HTTPException(status_code=404, detail="Percorso non valido")
        
        return FileResponse(
            path=str(image_path),
            media_type="image/jpeg",
            filename=filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.get("/product/{platform_id}/{product_id}/metadata")
@cached(
    ttl=TTL_PRESETS["product"],  # 6 ore
    key="image_metadata:{platform_id}:{product_id}",
    layer="hybrid"
)
async def get_product_image_metadata(
    platform_id: int = FastAPIPath(gt=0),
    product_id: int = FastAPIPath(gt=0)
):
    """
    Ottiene i metadati di un'immagine prodotto.
    
    - **platform_id**: ID della piattaforma
    - **product_id**: ID del prodotto
    """
    try:
        cache_service = await get_image_cache_service()
        metadata = await cache_service.get_image_metadata(platform_id, product_id)
        
        if not metadata:
            raise HTTPException(status_code=404, detail="Immagine non trovata")
        
        return metadata
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.post("/product/{platform_id}/batch/metadata")
async def get_batch_image_metadata(
    platform_id: int = FastAPIPath(gt=0),
    product_ids: list[int] = Query(..., description="Lista di ID prodotti")
):
    """
    Ottiene i metadati di più immagini in batch.
    
    - **platform_id**: ID della piattaforma
    - **product_ids**: Lista di ID prodotti
    """
    try:
        if len(product_ids) > 100:  # Limite per evitare abusi
            raise HTTPException(status_code=400, detail="Massimo 100 prodotti per richiesta")
        
        cache_service = await get_image_cache_service()
        metadata = await cache_service.get_batch_image_metadata(platform_id, product_ids)
        
        return {
            "platform_id": platform_id,
            "total_requested": len(product_ids),
            "found": len(metadata),
            "images": metadata
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.delete("/product/{platform_id}/{product_id}/cache")
async def invalidate_product_image_cache(
    platform_id: int = FastAPIPath(gt=0),
    product_id: int = FastAPIPath(gt=0)
):
    """
    Invalida la cache per un'immagine specifica.
    
    - **platform_id**: ID della piattaforma
    - **product_id**: ID del prodotto
    """
    try:
        cache_service = await get_image_cache_service()
        await cache_service.invalidate_product_image(platform_id, product_id)
        
        return {"message": f"Cache invalidata per prodotto {product_id}"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.delete("/product/{platform_id}/cache")
async def invalidate_platform_images_cache(
    platform_id: int = FastAPIPath(gt=0)
):
    """
    Invalida la cache per tutte le immagini di una piattaforma.
    
    - **platform_id**: ID della piattaforma
    """
    try:
        cache_service = await get_image_cache_service()
        await cache_service.invalidate_platform_images(platform_id)
        
        return {"message": f"Cache invalidata per piattaforma {platform_id}"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")


@router.get("/cache/stats")
async def get_image_cache_stats():
    """
    Ottiene le statistiche della cache delle immagini.
    """
    try:
        cache_service = await get_image_cache_service()
        stats = await cache_service.get_cache_stats()
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")