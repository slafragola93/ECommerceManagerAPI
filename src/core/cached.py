"""
Cache decorator and utilities for ECommerceManagerAPI
"""

import asyncio
import hashlib
import inspect
import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional, Union, List
from datetime import datetime

from .cache import get_cache_manager, CacheError
from .settings import get_cache_settings, TTL_PRESETS

logger = logging.getLogger(__name__)


def cached(
    ttl: Optional[int] = None,
    preset: Optional[str] = None,
    key: Optional[Union[str, Callable]] = None,
    layer: str = "auto",
    stale_ttl: Optional[int] = None,
    single_flight: bool = False,
    skip_cache: bool = False,
    tenant_from_user: bool = True,
    **kwargs
):
    """
    Cache decorator for functions and methods
    
    Args:
        ttl: Cache TTL in seconds
        preset: TTL preset name (from TTL_PRESETS)
        key: Cache key template or function to generate key
        layer: Cache layer ("auto", "memory", "redis")
        stale_ttl: TTL for stale-while-revalidate pattern
        single_flight: Prevent concurrent execution of same key
        skip_cache: Skip cache for this call (useful for testing)
        tenant_from_user: Extract tenant from user context
        **kwargs: Additional parameters for key generation
    
    Examples:
        @cached(ttl=3600, key="customer:{customer_id}")
        async def get_customer(customer_id: int):
            pass
        
        @cached(preset="orders_list", key="orders:list:{tenant}:{qhash}")
        async def get_orders_list(tenant: str, filters: dict):
            pass
    """
    
    def decorator(func: Callable) -> Callable:
        if not inspect.iscoroutinefunction(func):
            raise ValueError("cached decorator only works with async functions")
        
        @wraps(func)
        async def wrapper(*args, **func_kwargs):
            settings = get_cache_settings()
            if not settings.cache_enabled or skip_cache:
                return await func(*args, **func_kwargs)
            
            # Generate cache key
            cache_key = _generate_cache_key(
                func, args, func_kwargs, key, tenant_from_user, kwargs
            )
            
            if not cache_key:
                logger.warning(f"Could not generate cache key for {func.__name__}")
                return await func(*args, **func_kwargs)
            
            cache_manager = await get_cache_manager()
            
            # Single-flight pattern
            if single_flight:
                async with cache_manager.single_flight(cache_key):
                    # Check cache after acquiring lock
                    cached_result = await cache_manager.get(cache_key, layer)
                    if cached_result is not None:
                        logger.debug(f"Single-flight cache hit: {cache_key}")
                        return cached_result
                    
                    # Execute function
                    result = await func(*args, **func_kwargs)
                    await cache_manager.set(cache_key, result, ttl, preset, layer)
                    return result
            
            # Stale-while-revalidate pattern
            if stale_ttl:
                return await _stale_while_revalidate(
                    cache_manager, cache_key, func, args, func_kwargs, 
                    ttl, preset, layer, stale_ttl
                )
            
            # Standard read-through pattern
            try:
                # Try to get from cache
                cached_result = await cache_manager.get(cache_key, layer)
                if cached_result is not None:
                    logger.debug(f"Cache hit: {cache_key}")
                    return cached_result
                
                # Cache miss - execute function
                logger.debug(f"Cache miss: {cache_key}")
                result = await func(*args, **func_kwargs)
                
                # Store in cache
                await cache_manager.set(cache_key, result, ttl, preset, layer)
                
                return result
                
            except CacheError as e:
                logger.error(f"Cache error in {func.__name__}: {e}")
                # Fallback to direct execution
                return await func(*args, **func_kwargs)
        
        # Add cache invalidation method to function
        wrapper.invalidate_cache = lambda *args, **kwargs: _invalidate_function_cache(
            func, args, kwargs, key, tenant_from_user
        )
        
        return wrapper
    
    return decorator


async def _stale_while_revalidate(
    cache_manager, cache_key: str, func: Callable, args: tuple, 
    func_kwargs: dict, ttl: Optional[int], preset: Optional[str], 
    layer: str, stale_ttl: int
):
    """Implement stale-while-revalidate pattern"""
    
    # Try to get fresh value
    fresh_result = await cache_manager.get(cache_key, layer)
    if fresh_result is not None:
        logger.debug(f"Fresh cache hit: {cache_key}")
        return fresh_result
    
    # Try to get stale value
    stale_key = f"stale:{cache_key}"
    stale_result = await cache_manager.get(stale_key, layer)
    
    # Start background refresh if we have stale data
    if stale_result is not None:
        logger.debug(f"Serving stale data: {cache_key}")
        # Schedule background refresh
        asyncio.create_task(_background_refresh(
            cache_manager, cache_key, stale_key, func, args, func_kwargs, 
            ttl, preset, layer, stale_ttl
        ))
        return stale_result
    
    # No cache data - execute synchronously
    logger.debug(f"Cache miss, executing: {cache_key}")
    result = await func(*args, **func_kwargs)
    
    # Store both fresh and stale
    await cache_manager.set(cache_key, result, ttl, preset, layer)
    await cache_manager.set(stale_key, result, stale_ttl, layer=layer)
    
    return result


async def _background_refresh(
    cache_manager, cache_key: str, stale_key: str, func: Callable, 
    args: tuple, func_kwargs: dict, ttl: Optional[int], preset: Optional[str], 
    layer: str, stale_ttl: int
):
    """Background refresh for stale-while-revalidate"""
    try:
        logger.debug(f"Background refresh: {cache_key}")
        result = await func(*args, **func_kwargs)
        
        # Update both fresh and stale cache
        await cache_manager.set(cache_key, result, ttl, preset, layer)
        await cache_manager.set(stale_key, result, stale_ttl, layer=layer)
        
        logger.debug(f"Background refresh completed: {cache_key}")
        
    except Exception as e:
        logger.error(f"Background refresh failed for {cache_key}: {e}")


def _generate_cache_key(
    func: Callable, args: tuple, func_kwargs: dict, key_template: Optional[Union[str, Callable]],
    tenant_from_user: bool, extra_kwargs: dict
) -> Optional[str]:
    """Generate cache key for function call"""
    
    # Extract tenant from user context if needed
    tenant = None
    if tenant_from_user:
        tenant = _extract_tenant_from_args(args, func_kwargs)
    
    # Use custom key function if provided
    if callable(key_template):
        try:
            return key_template(*args, **func_kwargs, tenant=tenant)
        except Exception as e:
            logger.error(f"Key function error: {e}")
            return None
    
    # Use key template if provided
    if key_template:
        try:
            # Merge all parameters
            all_params = _extract_function_params(func, args, func_kwargs)
            if tenant:
                all_params["tenant"] = tenant
            all_params.update(extra_kwargs)
            
            return key_template.format(**all_params)
        except Exception as e:
            logger.error(f"Key template error: {e}")
            return None
    
    # Generate default key from function name and parameters
    try:
        params = _extract_function_params(func, args, func_kwargs)
        if tenant:
            params["tenant"] = tenant
        
        # Create query hash for complex parameters
        qhash = _create_query_hash(params)
        
        key_parts = [func.__name__]
        if tenant:
            key_parts.append(tenant)
        if qhash:
            key_parts.append(qhash)
        
        return ":".join(str(part) for part in key_parts)
        
    except Exception as e:
        logger.error(f"Default key generation error: {e}")
        return None


def _extract_tenant_from_args(args: tuple, func_kwargs: dict) -> Optional[str]:
    """Extract tenant from function arguments"""
    
    # Look for user dependency in arguments
    for arg in args:
        if isinstance(arg, dict) and "id" in arg:
            # User dependency dict
            return f"user_{arg['id']}"
    
    # Look in kwargs
    user = func_kwargs.get("user")
    if isinstance(user, dict) and "id" in user:
        return f"user_{user['id']}"
    
    # Look for tenant parameter
    tenant = func_kwargs.get("tenant")
    if tenant:
        return str(tenant)
    
    return "default"


def _extract_function_params(func: Callable, args: tuple, func_kwargs: dict) -> Dict[str, Any]:
    """Extract function parameters for key generation"""
    params = {}
    
    # Get function signature
    sig = inspect.signature(func)
    bound_args = sig.bind(*args, **func_kwargs)
    bound_args.apply_defaults()
    
    # Extract relevant parameters (exclude cache-unfriendly ones)
    exclude_params = {"user", "db", "session", "request", "response"}
    
    for param_name, param_value in bound_args.arguments.items():
        if param_name in exclude_params:
            continue
        
        # Handle special types
        if isinstance(param_value, (list, dict)):
            # Create hash for complex objects
            params[param_name] = _create_query_hash(param_value)
        elif isinstance(param_value, datetime):
            params[param_name] = param_value.isoformat()
        else:
            params[param_name] = param_value
    
    return params


def _create_query_hash(value: Any) -> str:
    """Create hash for query parameters"""
    try:
        if isinstance(value, dict):
            # Sort dict for consistent hashing
            sorted_items = sorted(value.items())
            value = sorted_items
        elif isinstance(value, list):
            # Sort list for consistent hashing
            value = sorted(value)
        
        serialized = str(value).encode('utf-8')
        return hashlib.md5(serialized).hexdigest()[:8]
    except Exception:
        return "invalid"


async def _invalidate_function_cache(
    func: Callable, args: tuple, kwargs: dict, key_template: Optional[Union[str, Callable]],
    tenant_from_user: bool
):
    """Invalidate cache for specific function call"""
    cache_key = _generate_cache_key(func, args, kwargs, key_template, tenant_from_user, {})
    if cache_key:
        cache_manager = await get_cache_manager()
        await cache_manager.delete_pattern(f"{cache_key}*")


# Utility functions for manual cache operations

async def invalidate_pattern(pattern: str, layer: str = "auto") -> int:
    """Invalidate all keys matching pattern"""
    cache_manager = await get_cache_manager()
    return await cache_manager.delete_pattern(pattern, layer)


async def invalidate_entity(entity_type: str, entity_id: Union[int, str], tenant: Optional[str] = None) -> int:
    """Invalidate cache for specific entity"""
    patterns = [
        f"{entity_type}:*:{entity_id}",
        f"{entity_type}s:list:*",  # Invalidate lists
    ]
    
    if tenant:
        patterns = [p.replace("*", f"{tenant}:*") for p in patterns]
    
    total_deleted = 0
    for pattern in patterns:
        deleted = await invalidate_pattern(pattern)
        total_deleted += deleted
    
    return total_deleted


async def invalidate_user_data(user_id: Union[int, str]) -> int:
    """Invalidate all cache data for specific user"""
    patterns = [
        f"*:user_{user_id}:*",
        f"*:{user_id}:*",
    ]
    
    total_deleted = 0
    for pattern in patterns:
        deleted = await invalidate_pattern(pattern)
        total_deleted += deleted
    
    return total_deleted


# Context manager for cache operations

class CacheContext:
    """Context manager for cache operations with automatic cleanup"""
    
    def __init__(self, patterns_to_invalidate: Optional[List[str]] = None):
        self.patterns = patterns_to_invalidate or []
        self.cache_manager = None
    
    async def __aenter__(self):
        self.cache_manager = await get_cache_manager()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and self.patterns:  # Only invalidate on success
            for pattern in self.patterns:
                await self.cache_manager.delete_pattern(pattern)
    
    async def invalidate(self, pattern: str):
        """Invalidate cache pattern"""
        if self.cache_manager:
            await self.cache_manager.delete_pattern(pattern)


# Decorator for cache invalidation on commit

def invalidate_on_commit(*patterns: str):
    """Decorator to invalidate cache patterns after successful commit"""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            with CacheContext(patterns) as ctx:
                result = await func(*args, **kwargs)
                # Invalidation happens automatically on context exit
                return result
        
        return wrapper
    
    return decorator
