"""
Cached Order Repository with cache integration
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException

from .order_repository import OrderRepository
from ..core.cached import cached, invalidate_entity, CacheContext
from ..core.settings import get_cache_settings
from ..schemas.order_schema import OrderSchema, OrderResponseSchema, AllOrderResponseSchema, OrderIdSchema, OrderUpdateSchema
from ..models import Order
from ..services import QueryUtils


class CachedOrderRepository(OrderRepository):
    """
    Order Repository with integrated caching
    Extends OrderRepository with cache decorators
    """
    
    def __init__(self, session: Session):
        super().__init__(session)
        self.settings = get_cache_settings()
    
    @cached(preset="orders_list", key="orders:list:{tenant}:{qhash}")
    async def get_all_cached(self, tenant: str, **filters) -> List[Order]:
        """Cached version of get_all"""
        return self.get_all(**filters)
    
    @cached(preset="order", key="order:{tenant}:{order_id}")
    async def get_by_id_cached(self, tenant: str, order_id: int) -> Optional[Order]:
        """Cached version of get_by_id"""
        return self.get_by_id(order_id)
    
    @cached(preset="orders_history", key="orders:history:{tenant}:{order_id}")
    async def get_order_history_cached(self, tenant: str, order_id: int) -> List[Dict[str, Any]]:
        """Cached version of order history"""
        return self.format_order_states(order_id)
    
    async def create_with_cache_invalidation(self, order_data: OrderSchema, tenant: str) -> int:
        """Create order with cache invalidation"""
        async with CacheContext([f"orders:list:{tenant}:*", f"orders:count:{tenant}"]) as ctx:
            order_id = self.create(order_data)
            
            # Invalidate related caches
            await ctx.invalidate(f"order:{tenant}:{order_id}")
            await ctx.invalidate(f"orders:history:{tenant}:{order_id}")
            
            return order_id
    
    async def update_with_cache_invalidation(self, order_id: int, order_data: OrderUpdateSchema, tenant: str) -> bool:
        """Update order with cache invalidation"""
        async with CacheContext([
            f"order:{tenant}:{order_id}",
            f"orders:list:{tenant}:*",
            f"orders:history:{tenant}:{order_id}"
        ]) as ctx:
            order = self.get_by_id(order_id)
            if not order:
                raise HTTPException(status_code=404, detail="Order not found")
            
            success = self.update(order, order_data)
            return success
    
    async def delete_with_cache_invalidation(self, order_id: int, tenant: str) -> bool:
        """Delete order with cache invalidation"""
        async with CacheContext([
            f"order:{tenant}:{order_id}",
            f"orders:list:{tenant}:*",
            f"orders:count:{tenant}",
            f"orders:history:{tenant}:{order_id}"
        ]) as ctx:
            order = self.get_by_id(order_id)
            if not order:
                raise HTTPException(status_code=404, detail="Order not found")
            
            success = self.delete(order)
            return success
    
    async def update_order_status_with_cache_invalidation(self, order_id: int, new_status_id: int, tenant: str) -> bool:
        """Update order status with cache invalidation"""
        async with CacheContext([
            f"order:{tenant}:{order_id}",
            f"orders:list:{tenant}:*",
            f"orders:history:{tenant}:{order_id}"
        ]) as ctx:
            success = self.update_order_status(order_id, new_status_id)
            return success
    
    async def invalidate_order_cache(self, order_id: int, tenant: str):
        """Manually invalidate order cache"""
        patterns = [
            f"order:{tenant}:{order_id}",
            f"orders:list:{tenant}:*",
            f"orders:history:{tenant}:{order_id}"
        ]
        
        for pattern in patterns:
            await invalidate_pattern(pattern)
    
    def get_all_with_cache(self, tenant: str, **filters) -> List[Order]:
        """Get all orders with automatic caching"""
        if not self.settings.cache_orders_enabled:
            return self.get_all(**filters)
        
        # Create query hash for cache key
        qhash = self._create_query_hash(filters)
        
        # Use cached method
        return self.get_all_cached(tenant, qhash=qhash, **filters)
    
    def get_by_id_with_cache(self, order_id: int, tenant: str) -> Optional[Order]:
        """Get order by ID with automatic caching"""
        if not self.settings.cache_orders_enabled:
            return self.get_by_id(order_id)
        
        return self.get_by_id_cached(tenant, order_id)
    
    def _create_query_hash(self, filters: Dict[str, Any]) -> str:
        """Create hash for query parameters"""
        import hashlib
        import json
        
        # Filter out None values and sort for consistent hashing
        filtered_params = {k: v for k, v in filters.items() if v is not None}
        sorted_params = sorted(filtered_params.items())
        
        param_str = json.dumps(sorted_params, default=str, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()[:8]


# Factory function for cached repository
def get_cached_order_repository(session: Session) -> CachedOrderRepository:
    """Get cached order repository instance"""
    return CachedOrderRepository(session)
