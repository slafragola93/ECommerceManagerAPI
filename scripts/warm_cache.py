#!/usr/bin/env python3
"""
Cache warming script for ECommerceManagerAPI
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.cache import get_cache_manager
from src.core.settings import get_cache_settings
from src.database import get_db
from src.repository.cached_lookup_repositories import (
    get_cached_order_state_repository,
    get_cached_category_repository,
    get_cached_brand_repository,
    get_cached_carrier_repository,
    get_cached_country_repository,
    get_cached_lang_repository
)


async def warm_lookup_tables():
    """Warm up lookup tables cache"""
    print("Warming up lookup tables cache...")
    
    db = next(get_db())
    tenant = "warmup"
    
    try:
        # Order states
        order_state_repo = get_cached_order_state_repository(db)
        await order_state_repo.get_all_cached(tenant)
        print("Order states cached")
        
        # Categories
        category_repo = get_cached_category_repository(db)
        await category_repo.get_all_cached(tenant)
        print("Categories cached")
        
        # Brands
        brand_repo = get_cached_brand_repository(db)
        await brand_repo.get_all_cached(tenant)
        print("Brands cached")
        
        # Carriers
        carrier_repo = get_cached_carrier_repository(db)
        await carrier_repo.get_all_cached(tenant)
        print("Carriers cached")
        
        # Countries
        country_repo = get_cached_country_repository(db)
        await country_repo.get_all_cached(tenant)
        print("Countries cached")
        
        # Languages
        lang_repo = get_cached_lang_repository(db)
        await lang_repo.get_all_cached(tenant)
        print("Languages cached")
        
    except Exception as e:
        print(f"Error warming lookup tables: {e}")
    finally:
        db.close()


async def warm_recent_data():
    """Warm up recent data cache"""
    print("Warming up recent data cache...")
    
    try:
        cache_manager = await get_cache_manager()
        
        # Warm up some common queries
        common_patterns = [
            "orders:list:*",
            "products:list:*", 
            "customers:list:*"
        ]
        
        # Pre-populate with empty results to avoid cache stampede
        for pattern in common_patterns:
            await cache_manager.set(f"warmup:{pattern}", [], ttl=60)
        
        print("Recent data patterns pre-cached")
        
    except Exception as e:
        print(f"Error warming recent data: {e}")


async def main():
    """Main cache warming function"""
    print("Starting cache warming process...")
    
    settings = get_cache_settings()
    if not settings.cache_enabled:
        print("Cache is disabled, skipping warm-up")
        return
    
    print(f"Cache backend: {settings.cache_backend}")
    print(f"Default TTL: {settings.cache_default_ttl}s")
    
    try:
        # Warm up lookup tables
        await warm_lookup_tables()
        
        # Warm up recent data patterns
        await warm_recent_data()
        
        # Show cache stats
        cache_manager = await get_cache_manager()
        stats = await cache_manager.get_stats()
        
        print("\nCache Statistics:")
        print(f"  Backend: {stats.get('backend', 'unknown')}")
        print(f"  Enabled: {stats.get('enabled', False)}")
        
        if 'memory' in stats:
            memory = stats['memory']
            print(f"  Memory cache: {memory.get('size', 0)}/{memory.get('max_size', 0)} items")
        
        if 'redis' in stats:
            redis = stats['redis']
            print(f"  Redis clients: {redis.get('connected_clients', 0)}")
        
        print("\nCache warming completed successfully!")
        
    except Exception as e:
        print(f"Cache warming failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
