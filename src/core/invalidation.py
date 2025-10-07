"""
Cache invalidation system with post-commit hooks
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any
from sqlalchemy import event
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

from .cache import get_cache_manager
from .cached import invalidate_pattern, invalidate_entity

logger = logging.getLogger(__name__)


class CacheInvalidationManager:
    """
    Manages cache invalidation with SQLAlchemy event hooks
    """
    
    def __init__(self):
        self._pending_invalidations: List[str] = {}
        self._cache_manager = None
        self._setup_sqlalchemy_events()
    
    def _setup_sqlalchemy_events(self):
        """Setup SQLAlchemy event listeners for cache invalidation"""
        
        # After commit event
        @event.listens_for(Session, 'after_commit')
        def receive_after_commit(session):
            """Handle cache invalidation after successful commit"""
            asyncio.create_task(self._process_pending_invalidations(session))
        
        # After rollback event
        @event.listens_for(Session, 'after_rollback')
        def receive_after_rollback(session):
            """Clear pending invalidations after rollback"""
            session_id = id(session)
            if session_id in self._pending_invalidations:
                del self._pending_invalidations[session_id]
                logger.debug(f"Cleared pending invalidations for session {session_id}")
    
    async def _process_pending_invalidations(self, session: Session):
        """Process pending cache invalidations after commit"""
        session_id = id(session)
        patterns = self._pending_invalidations.get(session_id, [])
        
        if patterns:
            logger.info(f"Processing {len(patterns)} pending invalidations for session {session_id}")
            
            if not self._cache_manager:
                self._cache_manager = await get_cache_manager()
            
            for pattern in patterns:
                try:
                    deleted = await self._cache_manager.delete_pattern(pattern)
                    logger.debug(f"Invalidated {deleted} keys matching pattern: {pattern}")
                except Exception as e:
                    logger.error(f"Error invalidating pattern {pattern}: {e}")
            
            # Clear pending invalidations
            del self._pending_invalidations[session_id]
    
    def add_pending_invalidation(self, session: Session, pattern: str):
        """Add cache invalidation pattern to be processed after commit"""
        session_id = id(session)
        if session_id not in self._pending_invalidations:
            self._pending_invalidations[session_id] = []
        
        self._pending_invalidations[session_id].append(pattern)
        logger.debug(f"Added pending invalidation: {pattern}")
    
    def add_pending_invalidations(self, session: Session, patterns: List[str]):
        """Add multiple cache invalidation patterns"""
        session_id = id(session)
        if session_id not in self._pending_invalidations:
            self._pending_invalidations[session_id] = []
        
        self._pending_invalidations[session_id].extend(patterns)
        logger.debug(f"Added {len(patterns)} pending invalidations")
    
    @asynccontextmanager
    async def invalidation_context(self, session: Session, patterns: Optional[List[str]] = None):
        """Context manager for cache invalidation"""
        patterns = patterns or []
        
        try:
            yield self
        finally:
            # Add patterns to pending invalidations
            if patterns:
                self.add_pending_invalidations(session, patterns)


# Global invalidation manager
_invalidation_manager: Optional[CacheInvalidationManager] = None


def get_invalidation_manager() -> CacheInvalidationManager:
    """Get global invalidation manager instance"""
    global _invalidation_manager
    if _invalidation_manager is None:
        _invalidation_manager = CacheInvalidationManager()
    return _invalidation_manager


# Utility functions for common invalidation patterns

def invalidate_on_create(session: Session, entity_type: str, tenant: Optional[str] = None):
    """Invalidate cache patterns when entity is created"""
    patterns = [
        f"{entity_type}s:list:*",
        f"{entity_type}s:count:*"
    ]
    
    if tenant:
        patterns = [p.replace("*", f"{tenant}:*") for p in patterns]
    
    manager = get_invalidation_manager()
    manager.add_pending_invalidations(session, patterns)
    
    logger.debug(f"Added create invalidation patterns for {entity_type}: {patterns}")


def invalidate_on_update(session: Session, entity_type: str, entity_id: Any, tenant: Optional[str] = None):
    """Invalidate cache patterns when entity is updated"""
    patterns = [
        f"{entity_type}:*:{entity_id}",
        f"{entity_type}s:list:*",
        f"{entity_type}s:count:*"
    ]
    
    if tenant:
        patterns = [p.replace("*", f"{tenant}:*") for p in patterns]
    
    manager = get_invalidation_manager()
    manager.add_pending_invalidations(session, patterns)
    
    logger.debug(f"Added update invalidation patterns for {entity_type}:{entity_id}: {patterns}")


def invalidate_on_delete(session: Session, entity_type: str, entity_id: Any, tenant: Optional[str] = None):
    """Invalidate cache patterns when entity is deleted"""
    patterns = [
        f"{entity_type}:*:{entity_id}",
        f"{entity_type}s:list:*",
        f"{entity_type}s:count:*"
    ]
    
    if tenant:
        patterns = [p.replace("*", f"{tenant}:*") for p in patterns]
    
    manager = get_invalidation_manager()
    manager.add_pending_invalidations(session, patterns)
    
    logger.debug(f"Added delete invalidation patterns for {entity_type}:{entity_id}: {patterns}")


def invalidate_order_related(session: Session, order_id: Any, tenant: Optional[str] = None):
    """Invalidate cache patterns related to order operations"""
    patterns = [
        f"order:*:{order_id}",
        f"orders:list:*",
        f"orders:count:*",
        f"orders:history:*:{order_id}",
        f"order_details:list:*",
        f"order_packages:list:*"
    ]
    
    if tenant:
        patterns = [p.replace("*", f"{tenant}:*") for p in patterns]
    
    manager = get_invalidation_manager()
    manager.add_pending_invalidations(session, patterns)
    
    logger.debug(f"Added order-related invalidation patterns for order:{order_id}: {patterns}")


def invalidate_customer_related(session: Session, customer_id: Any, tenant: Optional[str] = None):
    """Invalidate cache patterns related to customer operations"""
    patterns = [
        f"customer:*:{customer_id}",
        f"customers:list:*",
        f"customers:count:*",
        f"address:*:{customer_id}",
        f"addresses:list:*",
        # Also invalidate orders for this customer
        f"orders:list:*",
        f"orders:count:*"
    ]
    
    if tenant:
        patterns = [p.replace("*", f"{tenant}:*") for p in patterns]
    
    manager = get_invalidation_manager()
    manager.add_pending_invalidations(session, patterns)
    
    logger.debug(f"Added customer-related invalidation patterns for customer:{customer_id}: {patterns}")


def invalidate_product_related(session: Session, product_id: Any, tenant: Optional[str] = None):
    """Invalidate cache patterns related to product operations"""
    patterns = [
        f"product:*:{product_id}",
        f"products:list:*",
        f"products:count:*",
        # Also invalidate order details that might reference this product
        f"order_details:list:*"
    ]
    
    if tenant:
        patterns = [p.replace("*", f"{tenant}:*") for p in patterns]
    
    manager = get_invalidation_manager()
    manager.add_pending_invalidations(session, patterns)
    
    logger.debug(f"Added product-related invalidation patterns for product:{product_id}: {patterns}")


def invalidate_preventivo_related(session: Session, preventivo_id: Any, tenant: Optional[str] = None):
    """Invalidate cache patterns related to preventivo operations"""
    patterns = [
        f"quote:*:{preventivo_id}",
        f"quotes:list:*",
        f"quotes:count:*",
        # Also invalidate related orders if preventivo was converted
        f"orders:list:*",
        f"orders:count:*"
    ]
    
    if tenant:
        patterns = [p.replace("*", f"{tenant}:*") for p in patterns]
    
    manager = get_invalidation_manager()
    manager.add_pending_invalidations(session, patterns)
    
    logger.debug(f"Added preventivo-related invalidation patterns for preventivo:{preventivo_id}: {patterns}")


# Decorator for automatic invalidation

def auto_invalidate(entity_type: str, tenant_from_user: bool = True):
    """Decorator to automatically invalidate cache on entity operations"""
    
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            # Extract session and entity info
            session = None
            entity_id = None
            tenant = None
            
            # Try to extract session from arguments
            for arg in args:
                if isinstance(arg, Session):
                    session = arg
                    break
            
            # Try to extract from kwargs
            if not session:
                session = kwargs.get('session') or kwargs.get('db')
            
            # Extract tenant from user if needed
            if tenant_from_user:
                user = kwargs.get('user')
                if isinstance(user, dict) and 'id' in user:
                    tenant = f"user_{user['id']}"
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Add invalidation based on operation type
            if session and result:
                if func.__name__.startswith('create'):
                    invalidate_on_create(session, entity_type, tenant)
                elif func.__name__.startswith('update'):
                    # Try to extract entity ID from result
                    if hasattr(result, 'id'):
                        entity_id = result.id
                    elif isinstance(result, dict) and 'id' in result:
                        entity_id = result['id']
                    elif isinstance(result, int):
                        entity_id = result
                    
                    if entity_id:
                        invalidate_on_update(session, entity_type, entity_id, tenant)
                elif func.__name__.startswith('delete'):
                    # Try to extract entity ID from arguments
                    for arg in args:
                        if hasattr(arg, 'id'):
                            entity_id = arg.id
                            break
                    
                    if entity_id:
                        invalidate_on_delete(session, entity_type, entity_id, tenant)
            
            return result
        
        return wrapper
    
    return decorator


# Manual invalidation utilities

async def invalidate_all_cache():
    """Invalidate all cache (use with caution)"""
    cache_manager = await get_cache_manager()
    
    # Get all keys and delete them
    if cache_manager._redis_client:
        keys = await cache_manager._redis_client.keys("*")
        if keys:
            await cache_manager._redis_client.delete(*keys)
            logger.info(f"Invalidated {len(keys)} cache keys")
    
    # Clear memory cache
    if cache_manager._memory_cache:
        cache_manager._memory_cache.clear()
        logger.info("Cleared memory cache")


async def invalidate_tenant_cache(tenant: str):
    """Invalidate all cache for specific tenant"""
    patterns = [
        f"*:{tenant}:*",
        f"{tenant}:*"
    ]
    
    cache_manager = await get_cache_manager()
    total_deleted = 0
    
    for pattern in patterns:
        deleted = await cache_manager.delete_pattern(pattern)
        total_deleted += deleted
    
    logger.info(f"Invalidated {total_deleted} cache keys for tenant: {tenant}")
    return total_deleted


async def invalidate_user_cache(user_id: str):
    """Invalidate all cache for specific user"""
    patterns = [
        f"*:user_{user_id}:*",
        f"user_{user_id}:*"
    ]
    
    cache_manager = await get_cache_manager()
    total_deleted = 0
    
    for pattern in patterns:
        deleted = await cache_manager.delete_pattern(pattern)
        total_deleted += deleted
    
    logger.info(f"Invalidated {total_deleted} cache keys for user: {user_id}")
    return total_deleted
