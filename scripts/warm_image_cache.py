#!/usr/bin/env python3
"""
Script per il warm-up della cache delle immagini
"""

import asyncio
import sys
from pathlib import Path

# Aggiungi il path del progetto
sys.path.append(str(Path(__file__).parent.parent))

from src.database import get_db
from src.services.image_cache_service import get_image_cache_service
from src.repository.product_repository import ProductRepository
from src.core.settings import get_cache_settings
from sqlalchemy import text


async def warm_image_cache(platform_id: int, batch_size: int = 100, limit: int = None):
    """
    Pre-carica la cache per le immagini di una piattaforma
    
    Args:
        platform_id: ID della piattaforma
        batch_size: Dimensione del batch per il pre-caricamento
        limit: Limite massimo di prodotti da processare (None = tutti)
    """
    print(f"[WARM-UP] Inizio warm-up cache immagini per piattaforma {platform_id}")
    
    # Inizializza il servizio di cache
    cache_service = await get_image_cache_service()
    
    # Ottieni la lista dei prodotti
    db = next(get_db())
    product_repo = ProductRepository(db)
    
    # Query per ottenere i prodotti con immagini
    query_sql = f"""
        SELECT id_product, id_origin 
        FROM products 
        WHERE img_url IS NOT NULL 
        AND img_url != ''
        AND img_url LIKE '/media/product_images/{platform_id}/%'
        {'LIMIT ' + str(limit) if limit else ''}
    """
    
    products = product_repo._session.execute(text(query_sql)).fetchall()
    
    product_ids = [p.id_origin for p in products]
    print(f"[INFO] Trovati {len(product_ids)} prodotti con immagini")
    
    if not product_ids:
        print("[ERROR] Nessun prodotto trovato")
        return
    
    # Pre-carica la cache in batch
    total_batches = (len(product_ids) + batch_size - 1) // batch_size
    print(f"[INFO] Processando {total_batches} batch di {batch_size} prodotti")
    
    for i in range(0, len(product_ids), batch_size):
        batch = product_ids[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        
        print(f"[BATCH] {batch_num}/{total_batches}: {len(batch)} prodotti")
        
        try:
            # Pre-carica i metadati
            await cache_service.warm_cache_for_products(platform_id, batch, batch_size)
            print(f"[SUCCESS] Batch {batch_num} completato")
            
        except Exception as e:
            print(f"[ERROR] Errore nel batch {batch_num}: {e}")
    
    # Ottieni le statistiche finali
    stats = await cache_service.get_cache_stats()
    print(f"[STATS] Statistiche cache:")
    print(f"   - Immagini totali: {stats['images']['total_images']}")
    print(f"   - Immagini in cache: {stats['images']['cached_images']}")
    print(f"   - Immagini fallback: {stats['images']['fallback_images']}")
    
    print(f"[SUCCESS] Warm-up completato per piattaforma {platform_id}")


async def warm_all_platforms():
    """Pre-carica la cache per tutte le piattaforme"""
    print("[WARM-UP] Inizio warm-up cache per tutte le piattaforme")
    
    # Ottieni le piattaforme
    db = next(get_db())
    platforms = db.execute(text("SELECT id_platform FROM platforms")).fetchall()
    
    for platform in platforms:
        platform_id = platform.id_platform
        await warm_image_cache(platform_id)
        print(f"[SUCCESS] Piattaforma {platform_id} completata")
    
    print("[SUCCESS] Warm-up di tutte le piattaforme completato")


async def main():
    """Funzione principale"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Warm-up cache immagini")
    parser.add_argument("--platform-id", type=int, help="ID piattaforma specifica")
    parser.add_argument("--batch-size", type=int, default=100, help="Dimensione batch")
    parser.add_argument("--limit", type=int, help="Limite massimo prodotti")
    parser.add_argument("--all-platforms", action="store_true", help="Tutte le piattaforme")
    
    args = parser.parse_args()
    
    if args.all_platforms:
        await warm_all_platforms()
    elif args.platform_id:
        await warm_image_cache(args.platform_id, args.batch_size, args.limit)
    else:
        print("[ERROR] Specifica --platform-id o --all-platforms")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
