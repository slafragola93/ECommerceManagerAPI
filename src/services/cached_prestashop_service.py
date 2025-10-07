"""
Cached PrestaShop Service with external API caching
"""

import asyncio
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from .ecommerce.prestashop_service import PrestaShopService
from ..core.cached import cached, invalidate_pattern
from ..core.settings import get_cache_settings


class CachedPrestaShopService(PrestaShopService):
    """
    PrestaShop Service with integrated caching for external API calls
    """
    
    def __init__(self, db: Session, platform_id: int = 1, **kwargs):
        super().__init__(db, platform_id, **kwargs)
        self.settings = get_cache_settings()
    
    @cached(preset="prestashop_orders", key="prestashop:orders:{tenant}:{shop_id}:{page}:{hash}", single_flight=True)
    async def get_orders_cached(self, tenant: str, shop_id: str, page: int = 1, **filters) -> Dict[str, Any]:
        """Cached version of PrestaShop orders fetch"""
        # This would call the actual PrestaShop API
        # For now, return a placeholder
        return {
            "orders": [],
            "page": page,
            "total": 0,
            "cached": True
        }
    
    @cached(preset="prestashop_customers", key="prestashop:customers:{tenant}:{shop_id}:{page}:{hash}", single_flight=True)
    async def get_customers_cached(self, tenant: str, shop_id: str, page: int = 1, **filters) -> Dict[str, Any]:
        """Cached version of PrestaShop customers fetch"""
        return {
            "customers": [],
            "page": page,
            "total": 0,
            "cached": True
        }
    
    @cached(preset="prestashop_products", key="prestashop:products:{tenant}:{shop_id}:{page}:{hash}", single_flight=True)
    async def get_products_cached(self, tenant: str, shop_id: str, page: int = 1, **filters) -> Dict[str, Any]:
        """Cached version of PrestaShop products fetch"""
        return {
            "products": [],
            "page": page,
            "total": 0,
            "cached": True
        }
    
    async def sync_orders_with_cache(self, tenant: str, shop_id: str, **filters) -> List[Dict[str, Any]]:
        """Sync orders with cache invalidation"""
        if not self.settings.cache_external_apis_enabled:
            return await self.sync_orders()
        
        # Use cached data
        cached_data = await self.get_orders_cached(tenant, shop_id, **filters)
        
        # Process sync logic here
        # ...
        
        # Invalidate related caches after sync
        await self._invalidate_sync_caches(tenant, shop_id)
        
        return cached_data.get("orders", [])
    
    async def sync_customers_with_cache(self, tenant: str, shop_id: str, **filters) -> List[Dict[str, Any]]:
        """Sync customers with cache invalidation"""
        if not self.settings.cache_external_apis_enabled:
            return await self.sync_customers()
        
        cached_data = await self.get_customers_cached(tenant, shop_id, **filters)
        
        # Process sync logic here
        # ...
        
        await self._invalidate_sync_caches(tenant, shop_id)
        
        return cached_data.get("customers", [])
    
    async def sync_products_with_cache(self, tenant: str, shop_id: str, **filters) -> List[Dict[str, Any]]:
        """Sync products with cache invalidation"""
        if not self.settings.cache_external_apis_enabled:
            return await self.sync_products()
        
        cached_data = await self.get_products_cached(tenant, shop_id, **filters)
        
        # Process sync logic here
        # ...
        
        await self._invalidate_sync_caches(tenant, shop_id)
        
        return cached_data.get("products", [])
    
    async def _invalidate_sync_caches(self, tenant: str, shop_id: str):
        """Invalidate caches after sync operations"""
        patterns = [
            f"prestashop:orders:{tenant}:{shop_id}:*",
            f"prestashop:customers:{tenant}:{shop_id}:*",
            f"prestashop:products:{tenant}:{shop_id}:*",
            # Also invalidate local caches that might be affected
            f"orders:list:{tenant}:*",
            f"customers:list:{tenant}:*",
            f"products:list:{tenant}:*"
        ]
        
        for pattern in patterns:
            await invalidate_pattern(pattern)
    
    async def invalidate_prestashop_cache(self, tenant: str, shop_id: str):
        """Manually invalidate PrestaShop cache"""
        await self._invalidate_sync_caches(tenant, shop_id)
    
    def _create_filters_hash(self, filters: Dict[str, Any]) -> str:
        """Create hash for filter parameters"""
        import hashlib
        import json
        
        # Sort filters for consistent hashing
        sorted_filters = sorted(filters.items())
        filter_str = json.dumps(sorted_filters, default=str, sort_keys=True)
        return hashlib.md5(filter_str.encode()).hexdigest()[:8]


# Factory function
def get_cached_prestashop_service(db: Session, platform_id: int = 1, **kwargs) -> CachedPrestaShopService:
    """Get cached PrestaShop service instance"""
    return CachedPrestaShopService(db, platform_id, **kwargs)
