"""
Servizio di caching per le immagini dei prodotti
Integra con il sistema di caching esistente
"""

import asyncio
import hashlib
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from src.core.cache import get_cache_manager
from src.core.cached import cached
from src.core.settings import TTL_PRESETS


class ImageCacheService:
    """
    Servizio per il caching delle immagini dei prodotti
    """
    
    def __init__(self):
        self.cache_manager = None
        self.base_path = Path("media/product_images")
    
    async def initialize(self):
        """Inizializza il servizio di cache"""
        self.cache_manager = await get_cache_manager()
    
    @cached(
        ttl=TTL_PRESETS["product"],  # 6 ore
        key="image_metadata:{platform_id}:{product_id}",
        layer="hybrid"
    )
    async def get_image_metadata(self, platform_id: int, product_id: int) -> Optional[Dict[str, Any]]:
        """
        Ottiene i metadati dell'immagine di un prodotto dal cache
        
        Args:
            platform_id: ID della piattaforma
            product_id: ID del prodotto
            
        Returns:
            Dict con metadati dell'immagine o None se non trovata
        """
        # Genera il percorso dell'immagine
        image_path = self.base_path / str(platform_id) / f"product_{product_id}.jpg"
        fallback_path = self.base_path / "fallback" / "product_not_found.jpg"
        
        # Controlla se l'immagine esiste
        if image_path.exists():
            stat = image_path.stat()
            return {
                "exists": True,
                "path": str(image_path),
                "relative_url": f"/media/product_images/{platform_id}/product_{product_id}.jpg",
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "is_fallback": False
            }
        elif fallback_path.exists():
            stat = fallback_path.stat()
            return {
                "exists": True,
                "path": str(fallback_path),
                "relative_url": "/media/product_images/fallback/product_not_found.jpg",
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "is_fallback": True
            }
        
        return None
    
    @cached(
        ttl=TTL_PRESETS["products_list"],  # 1 minuto
        key="images_batch:{platform_id}:{product_ids_hash}",
        layer="memory"  # Solo memory per batch queries
    )
    async def get_batch_image_metadata(self, platform_id: int, product_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """
        Ottiene i metadati di più immagini in batch
        
        Args:
            platform_id: ID della piattaforma
            product_ids: Lista di ID prodotti
            
        Returns:
            Dict con metadati per ogni prodotto
        """
        results = {}
        
        for product_id in product_ids:
            metadata = await self.get_image_metadata(platform_id, product_id)
            if metadata:
                results[product_id] = metadata
        
        return results
    
    async def invalidate_product_image(self, platform_id: int, product_id: int):
        """
        Invalida la cache per un'immagine specifica
        
        Args:
            platform_id: ID della piattaforma
            product_id: ID del prodotto
        """
        if not self.cache_manager:
            await self.initialize()
        
        # Invalida cache specifica
        cache_key = f"image_metadata:{platform_id}:{product_id}"
        await self.cache_manager.delete(cache_key)
        
        # Invalida batch cache che potrebbero contenere questo prodotto
        await self.cache_manager.delete_pattern(f"images_batch:{platform_id}:*")
    
    async def invalidate_platform_images(self, platform_id: int):
        """
        Invalida tutte le immagini di una piattaforma
        
        Args:
            platform_id: ID della piattaforma
        """
        if not self.cache_manager:
            await self.initialize()
        
        # Invalida tutte le cache delle immagini per questa piattaforma
        patterns = [
            f"image_metadata:{platform_id}:*",
            f"images_batch:{platform_id}:*"
        ]
        
        for pattern in patterns:
            await self.cache_manager.delete_pattern(pattern)
    
    async def warm_cache_for_products(self, platform_id: int, product_ids: List[int], batch_size: int = 50):
        """
        Pre-carica la cache per una lista di prodotti
        
        Args:
            platform_id: ID della piattaforma
            product_ids: Lista di ID prodotti
            batch_size: Dimensione del batch per il pre-caricamento
        """
        # Dividi in batch per evitare timeout
        for i in range(0, len(product_ids), batch_size):
            batch = product_ids[i:i + batch_size]
            
            # Pre-carica i metadati
            await self.get_batch_image_metadata(platform_id, batch)
            
            # Pre-carica i singoli metadati per popolare la cache
            tasks = [
                self.get_image_metadata(platform_id, product_id) 
                for product_id in batch
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Ottiene le statistiche della cache delle immagini
        
        Returns:
            Dict con statistiche della cache
        """
        if not self.cache_manager:
            await self.initialize()
        
        stats = await self.cache_manager.get_stats()
        
        # Aggiungi statistiche specifiche per le immagini
        image_stats = {
            "total_images": 0,
            "cached_images": 0,
            "fallback_images": 0,
            "cache_hit_rate": 0.0
        }
        
        # Conta le immagini nella directory
        if self.base_path.exists():
            for platform_dir in self.base_path.iterdir():
                if platform_dir.is_dir() and platform_dir.name != "fallback":
                    image_files = list(platform_dir.glob("product_*.jpg"))
                    image_stats["total_images"] += len(image_files)
        
        # Conta le immagini di fallback
        fallback_dir = self.base_path / "fallback"
        if fallback_dir.exists():
            fallback_files = list(fallback_dir.glob("*.jpg"))
            image_stats["fallback_images"] = len(fallback_files)
        
        stats["images"] = image_stats
        return stats


# Istanza globale del servizio
_image_cache_service: Optional[ImageCacheService] = None


async def get_image_cache_service() -> ImageCacheService:
    """Ottiene l'istanza globale del servizio di cache delle immagini"""
    global _image_cache_service
    if _image_cache_service is None:
        _image_cache_service = ImageCacheService()
        await _image_cache_service.initialize()
    return _image_cache_service
