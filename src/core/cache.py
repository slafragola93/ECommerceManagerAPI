"""
Multilayer cache manager for ECommerceManagerAPI
"""

import asyncio
import hashlib
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime, timedelta

import orjson
from cachetools import TTLCache
import redis.asyncio as aioredis

from .settings import get_cache_settings, TTL_PRESETS

logger = logging.getLogger(__name__)


class CacheError(Exception):
    """Cache operation error"""
    pass


class CacheManager:
    """
    Multilayer cache manager with Redis + in-memory support
    """
    
    def __init__(self):
        self.settings = get_cache_settings()
        self._redis_client: Optional[aioredis.Redis] = None
        self._memory_cache: Optional[TTLCache] = None
        self._lock_cache: Dict[str, asyncio.Lock] = {}
        self._circuit_breaker = CircuitBreaker(
            error_threshold=self.settings.cache_error_threshold,
            recovery_timeout=self.settings.cache_recovery_timeout
        )
        
    async def initialize(self) -> None:
        """Initialize cache backends"""
        if not self.settings.cache_enabled:
            logger.info("Cache disabled by configuration")
            return
            
        # Initialize memory cache
        if self.settings.cache_backend in ["memory", "hybrid"]:
            self._memory_cache = TTLCache(
                maxsize=self.settings.cache_max_mem_items,
                ttl=self.settings.cache_default_ttl
            )
            logger.info(f"Memory cache initialized with {self.settings.cache_max_mem_items} max items")
        
        # Initialize Redis cache
        if self.settings.cache_backend in ["redis", "hybrid"]:
            try:
                self._redis_client = aioredis.from_url(
                    self.settings.redis_url,
                    max_connections=self.settings.redis_max_connections,
                    retry_on_timeout=self.settings.redis_retry_on_timeout,
                    socket_keepalive=self.settings.redis_socket_keepalive,
                    socket_keepalive_options=self.settings.redis_socket_keepalive_options,
                    decode_responses=False  # Keep binary for orjson
                )
                
                # Test connection
                await self._redis_client.ping()
                logger.info(f"Redis cache initialized at {self.settings.redis_url}")
                
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}, falling back to memory-only")
                self._redis_client = None
                if self.settings.cache_backend == "redis":
                    self.settings.cache_backend = "memory"
    
    async def close(self) -> None:
        """Close cache connections"""
        if self._redis_client:
            await self._redis_client.close()
        logger.info("Cache connections closed")
    
    def _build_key(self, namespace: str, **params) -> str:
        """Build cache key with namespace and parameters"""
        # Normalize and sort parameters for consistent keys
        sorted_params = sorted(params.items())
        param_str = ":".join(f"{k}={v}" for k, v in sorted_params if v is not None)
        
        # Create hash for long keys
        if len(param_str) > 100:
            param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
            key = f"{self.settings.cache_key_salt}:{namespace}:{param_hash}"
        else:
            key = f"{self.settings.cache_key_salt}:{namespace}:{param_str}"
        
        return key
    
    def _get_ttl(self, ttl: Optional[int] = None, preset: Optional[str] = None) -> int:
        """Get TTL value from preset or parameter"""
        if ttl is not None:
            return ttl
        if preset and preset in TTL_PRESETS:
            return TTL_PRESETS[preset]
        return self.settings.cache_default_ttl
    
    async def get(self, key: str, layer: str = "auto") -> Optional[Any]:
        """Get value from cache"""
        if not self.settings.cache_enabled:
            return None
            
        try:
            with self._circuit_breaker:
                if layer in ["auto", "memory"] and self._memory_cache:
                    # Try memory cache first
                    value = self._memory_cache.get(key)
                    if value is not None:
                        logger.debug(f"Memory cache hit: {key}")
                        return self._deserialize(value)
                
                if layer in ["auto", "redis"] and self._redis_client:
                    # Try Redis cache
                    serialized = await self._redis_client.get(key)
                    if serialized:
                        value = self._deserialize(serialized)
                        logger.debug(f"Redis cache hit: {key}")
                        
                        # Populate memory cache if available
                        if self._memory_cache and layer == "auto":
                            self._memory_cache[key] = serialized
                        
                        return value
                        
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            self._circuit_breaker.record_error()
            
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, 
                  preset: Optional[str] = None, layer: str = "auto") -> bool:
        """Set value in cache"""
        if not self.settings.cache_enabled:
            return False
            
        ttl_seconds = self._get_ttl(ttl, preset)
        
        try:
            with self._circuit_breaker:
                serialized = self._serialize(value)
                
                # Check size limit
                if len(serialized) > self.settings.cache_max_value_size:
                    logger.warning(f"Value too large for cache: {len(serialized)} bytes")
                    return False
                
                success = True
                
                # Set in memory cache
                if layer in ["auto", "memory"] and self._memory_cache:
                    self._memory_cache[key] = serialized
                
                # Set in Redis cache
                if layer in ["auto", "redis"] and self._redis_client:
                    await self._redis_client.setex(key, ttl_seconds, serialized)
                
                logger.debug(f"Cache set: {key} (TTL: {ttl_seconds}s)")
                return success
                
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            self._circuit_breaker.record_error()
            return False
    
    async def delete(self, key: str, layer: str = "auto") -> bool:
        """Delete key from cache"""
        if not self.settings.cache_enabled:
            return False
            
        try:
            success = True
            
            # Delete from memory cache
            if layer in ["auto", "memory"] and self._memory_cache:
                self._memory_cache.pop(key, None)
            
            # Delete from Redis cache
            if layer in ["auto", "redis"] and self._redis_client:
                await self._redis_client.delete(key)
            
            logger.debug(f"Cache delete: {key}")
            return success
            
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def delete_pattern(self, pattern: str, layer: str = "redis") -> int:
        """Delete keys matching pattern"""
        if not self.settings.cache_enabled or not self._redis_client:
            return 0
            
        try:
            keys = await self._redis_client.keys(pattern)
            if keys:
                deleted = await self._redis_client.delete(*keys)
                logger.info(f"Deleted {deleted} keys matching pattern: {pattern}")
                return deleted
        except Exception as e:
            logger.error(f"Cache delete pattern error for {pattern}: {e}")
            
        return 0
    
    async def try_acquire_lock(self, key: str, ttl: int = 60) -> bool:
        """Try to acquire distributed lock"""
        if not self._redis_client:
            return True  # No Redis, assume single instance
            
        lock_key = f"lock:{key}"
        try:
            # SET with NX and EX for atomic lock with TTL
            result = await self._redis_client.set(
                lock_key, 
                "1", 
                nx=True,  # Only set if not exists
                ex=ttl    # Expire after TTL seconds
            )
            return result is not None
        except Exception as e:
            logger.error(f"Lock acquire error for {key}: {e}")
            return False
    
    async def release_lock(self, key: str) -> bool:
        """Release distributed lock"""
        if not self._redis_client:
            return True
            
        lock_key = f"lock:{key}"
        try:
            await self._redis_client.delete(lock_key)
            return True
        except Exception as e:
            logger.error(f"Lock release error for {key}: {e}")
            return False
    
    @asynccontextmanager
    async def single_flight(self, key: str, ttl: int = 60):
        """Single-flight context manager to prevent duplicate operations"""
        # Process-level lock
        if key not in self._lock_cache:
            self._lock_cache[key] = asyncio.Lock()
        
        async with self._lock_cache[key]:
            # Try distributed lock
            if await self.try_acquire_lock(key, ttl):
                try:
                    yield True  # Lock acquired
                finally:
                    await self.release_lock(key)
            else:
                yield False  # Another instance is handling this
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value to bytes"""
        try:
            return orjson.dumps(value, default=self._json_default)
        except Exception as e:
            logger.error(f"Serialization error: {e}")
            raise CacheError(f"Failed to serialize value: {e}")
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to value"""
        try:
            return orjson.loads(data)
        except Exception as e:
            logger.error(f"Deserialization error: {e}")
            raise CacheError(f"Failed to deserialize value: {e}")
    
    def _json_default(self, obj):
        """Default JSON serializer for special types"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, 'isoformat'):  # date objects
            return obj.isoformat()
        
        # Handle SQLAlchemy models
        if hasattr(obj, '__dict__') and hasattr(obj, '_sa_instance_state'):
            # Convert SQLAlchemy model to dict
            return {key: value for key, value in obj.__dict__.items() 
                   if not key.startswith('_')}
        
        # Handle objects with __dict__ (like dataclasses)
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        
        # Try to convert to string as fallback
        try:
            return str(obj)
        except:
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            "enabled": self.settings.cache_enabled,
            "backend": self.settings.cache_backend,
            "circuit_breaker": self._circuit_breaker.get_status()
        }
        
        if self._memory_cache:
            stats["memory"] = {
                "size": len(self._memory_cache),
                "max_size": self._memory_cache.maxsize,
                "ttl": self._memory_cache.ttl
            }
        
        if self._redis_client:
            try:
                info = await self._redis_client.info()
                stats["redis"] = {
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory_human": info.get("used_memory_human", "0B"),
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0)
                }
            except Exception as e:
                stats["redis"] = {"error": str(e)}
        
        return stats


class CircuitBreaker:
    """Circuit breaker for cache operations"""
    
    def __init__(self, error_threshold: float = 0.5, recovery_timeout: int = 300):
        self.error_threshold = error_threshold
        self.recovery_timeout = recovery_timeout
        self.error_count = 0
        self.request_count = 0
        self.last_error_time = None
        self.state = "closed"  # closed, open, half_open
    
    def record_error(self):
        """Record a cache error"""
        self.error_count += 1
        self.last_error_time = time.time()
        self.request_count += 1
        
        if self.request_count > 10:  # Minimum sample size
            error_rate = self.error_count / self.request_count
            if error_rate > self.error_threshold:
                self.state = "open"
                logger.warning(f"Cache circuit breaker opened (error rate: {error_rate:.2f})")
    
    def record_success(self):
        """Record a successful cache operation"""
        self.request_count += 1
        if self.state == "half_open":
            self.state = "closed"
            self.error_count = 0
            self.request_count = 0
            logger.info("Cache circuit breaker closed")
    
    def should_allow_request(self) -> bool:
        """Check if requests should be allowed"""
        if self.state == "closed":
            return True
        
        if self.state == "open":
            if time.time() - self.last_error_time > self.recovery_timeout:
                self.state = "half_open"
                logger.info("Cache circuit breaker half-open")
                return True
            return False
        
        return True  # half_open
    
    def __enter__(self):
        if not self.should_allow_request():
            raise CacheError("Cache circuit breaker is open")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.record_success()
        else:
            self.record_error()
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status"""
        return {
            "state": self.state,
            "error_count": self.error_count,
            "request_count": self.request_count,
            "error_rate": self.error_count / max(self.request_count, 1),
            "last_error_time": self.last_error_time
        }


# Global cache instance
_cache_manager: Optional[CacheManager] = None


async def get_cache_manager() -> CacheManager:
    """Get global cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
        await _cache_manager.initialize()
    return _cache_manager


async def close_cache_manager():
    """Close global cache manager"""
    global _cache_manager
    if _cache_manager:
        await _cache_manager.close()
        _cache_manager = None
