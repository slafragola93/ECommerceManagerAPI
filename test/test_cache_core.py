"""
Unit tests for cache core functionality
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.core.cache import CacheManager, CacheError, CircuitBreaker
from src.core.cached import cached, invalidate_pattern, invalidate_entity
from src.core.settings import CacheSettings


class TestCacheManager:
    """Test CacheManager functionality"""
    
    @pytest.fixture
    async def cache_manager(self):
        """Create cache manager for testing"""
        manager = CacheManager()
        # Mock Redis client
        manager._redis_client = AsyncMock()
        manager._redis_client.ping.return_value = True
        manager._redis_client.get.return_value = None
        manager._redis_client.setex.return_value = True
        manager._redis_client.delete.return_value = 1
        manager._redis_client.keys.return_value = []
        manager._redis_client.info.return_value = {"connected_clients": 1}
        
        # Initialize memory cache
        manager._memory_cache = MagicMock()
        manager._memory_cache.get.return_value = None
        manager._memory_cache.__setitem__ = MagicMock()
        manager._memory_cache.__getitem__ = MagicMock()
        manager._memory_cache.pop.return_value = None
        
        await manager.initialize()
        yield manager
        await manager.close()
    
    def test_build_key(self, cache_manager):
        """Test cache key building"""
        key = cache_manager._build_key("test", param1="value1", param2="value2")
        assert "test" in key
        assert "value1" in key
        assert "value2" in key
        
        # Test with long parameters (should create hash)
        long_param = "x" * 200
        key = cache_manager._build_key("test", long_param=long_param)
        assert len(key) < 150  # Should be hashed
    
    def test_get_ttl(self, cache_manager):
        """Test TTL calculation"""
        # Test with explicit TTL
        assert cache_manager._get_ttl(ttl=60) == 60
        
        # Test with preset
        assert cache_manager._get_ttl(preset="order_states") == 86400
        
        # Test default
        assert cache_manager._get_ttl() == cache_manager.settings.cache_default_ttl
    
    @pytest.mark.asyncio
    async def test_get_set_memory(self, cache_manager):
        """Test get/set operations in memory cache"""
        key = "test_key"
        value = {"test": "data"}
        
        # Test set
        result = await cache_manager.set(key, value, layer="memory")
        assert result is True
        
        # Test get
        cache_manager._memory_cache.get.return_value = b'{"test": "data"}'
        cached_value = await cache_manager.get(key, layer="memory")
        assert cached_value == value
    
    @pytest.mark.asyncio
    async def test_get_set_redis(self, cache_manager):
        """Test get/set operations in Redis cache"""
        key = "test_key"
        value = {"test": "data"}
        
        # Test set
        result = await cache_manager.set(key, value, layer="redis")
        assert result is True
        cache_manager._redis_client.setex.assert_called_once()
        
        # Test get
        cache_manager._redis_client.get.return_value = b'{"test": "data"}'
        cached_value = await cache_manager.get(key, layer="redis")
        assert cached_value == value
    
    @pytest.mark.asyncio
    async def test_delete(self, cache_manager):
        """Test delete operations"""
        key = "test_key"
        
        result = await cache_manager.delete(key, layer="auto")
        assert result is True
        
        # Should delete from both memory and Redis
        cache_manager._memory_cache.pop.assert_called_once()
        cache_manager._redis_client.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_lock_operations(self, cache_manager):
        """Test distributed lock operations"""
        key = "test_lock"
        
        # Test acquire lock
        cache_manager._redis_client.set.return_value = "OK"
        result = await cache_manager.try_acquire_lock(key, 60)
        assert result is True
        
        # Test release lock
        result = await cache_manager.release_lock(key)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_single_flight(self, cache_manager):
        """Test single-flight pattern"""
        key = "test_single_flight"
        
        cache_manager._redis_client.set.return_value = "OK"
        cache_manager._redis_client.delete.return_value = 1
        
        async with cache_manager.single_flight(key, 60) as acquired:
            assert acquired is True
    
    @pytest.mark.asyncio
    async def test_circuit_breaker(self, cache_manager):
        """Test circuit breaker functionality"""
        cb = CircuitBreaker(error_threshold=0.5, recovery_timeout=1)
        
        # Record some errors
        for _ in range(6):
            cb.record_success()
        for _ in range(6):
            cb.record_error()
        
        # Circuit should be open
        assert cb.state == "open"
        assert not cb.should_allow_request()
        
        # Wait for recovery
        time.sleep(1.1)
        assert cb.should_allow_request()
        assert cb.state == "half_open"


class TestCachedDecorator:
    """Test @cached decorator"""
    
    @pytest.fixture
    def mock_cache_manager(self):
        """Mock cache manager"""
        with patch('src.core.cached.get_cache_manager') as mock:
            manager = AsyncMock()
            manager.get.return_value = None
            manager.set.return_value = True
            mock.return_value = manager
            yield manager
    
    @pytest.mark.asyncio
    async def test_cached_decorator_basic(self, mock_cache_manager):
        """Test basic cached decorator functionality"""
        
        @cached(ttl=60, key="test:{param}")
        async def test_function(param: str):
            return f"result_{param}"
        
        # First call should cache miss
        result = await test_function("test")
        assert result == "result_test"
        
        # Verify cache operations
        mock_cache_manager.get.assert_called_once()
        mock_cache_manager.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cached_decorator_hit(self, mock_cache_manager):
        """Test cached decorator with cache hit"""
        
        # Mock cache hit
        mock_cache_manager.get.return_value = "cached_result"
        
        @cached(ttl=60, key="test:{param}")
        async def test_function(param: str):
            return f"result_{param}"
        
        result = await test_function("test")
        assert result == "cached_result"
        
        # Should not call set on cache hit
        mock_cache_manager.set.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_cached_decorator_with_tenant(self, mock_cache_manager):
        """Test cached decorator with tenant extraction"""
        
        @cached(ttl=60, key="test:{tenant}:{param}", tenant_from_user=True)
        async def test_function(param: str, user=None):
            return f"result_{param}"
        
        user = {"id": 123}
        result = await test_function("test", user=user)
        assert result == "result_test"
        
        # Verify cache key includes tenant
        call_args = mock_cache_manager.set.call_args
        cache_key = call_args[0][0]
        assert "user_123" in cache_key
    
    @pytest.mark.asyncio
    async def test_cached_decorator_single_flight(self, mock_cache_manager):
        """Test cached decorator with single-flight pattern"""
        
        @cached(ttl=60, key="test:{param}", single_flight=True)
        async def test_function(param: str):
            return f"result_{param}"
        
        # Mock lock operations
        mock_cache_manager.try_acquire_lock.return_value = True
        mock_cache_manager.release_lock.return_value = True
        
        result = await test_function("test")
        assert result == "result_test"
        
        # Should try to acquire lock
        mock_cache_manager.try_acquire_lock.assert_called_once()


class TestInvalidation:
    """Test cache invalidation functionality"""
    
    @pytest.fixture
    def mock_cache_manager(self):
        """Mock cache manager for invalidation tests"""
        with patch('src.core.cached.get_cache_manager') as mock:
            manager = AsyncMock()
            manager.delete_pattern.return_value = 5
            mock.return_value = manager
            yield manager
    
    @pytest.mark.asyncio
    async def test_invalidate_pattern(self, mock_cache_manager):
        """Test pattern-based invalidation"""
        result = await invalidate_pattern("test:*")
        assert result == 5
        mock_cache_manager.delete_pattern.assert_called_once_with("test:*")
    
    @pytest.mark.asyncio
    async def test_invalidate_entity(self, mock_cache_manager):
        """Test entity-based invalidation"""
        result = await invalidate_entity("order", 123, "tenant1")
        assert result == 10  # 2 patterns * 5 deleted each
        
        # Should call delete_pattern twice (entity and list)
        assert mock_cache_manager.delete_pattern.call_count == 2


class TestSettings:
    """Test cache settings"""
    
    def test_default_settings(self):
        """Test default cache settings"""
        settings = CacheSettings()
        
        assert settings.cache_enabled is True
        assert settings.cache_backend == "hybrid"
        assert settings.cache_default_ttl == 300
        assert settings.redis_url == "redis://localhost:6379/0"
    
    def test_ttl_presets(self):
        """Test TTL presets"""
        from src.core.settings import TTL_PRESETS
        
        assert TTL_PRESETS["order_states"] == 86400
        assert TTL_PRESETS["order"] == 120
        assert TTL_PRESETS["prestashop_orders"] == 120


class TestObservability:
    """Test observability and metrics"""
    
    def test_metrics_recording(self):
        """Test metrics recording"""
        from src.core.observability import CacheMetrics
        
        metrics = CacheMetrics()
        
        # Record some metrics
        metrics.record_hit("memory", "test_pattern")
        metrics.record_miss("redis", "test_pattern")
        metrics.record_latency("get", "memory", 10.5)
        
        # Check counters
        assert metrics._counters["cache_hit_total_memory_test_pattern"] == 1
        assert metrics._counters["cache_miss_total_redis_test_pattern"] == 1
        
        # Check hit rate
        hit_rate = metrics.get_hit_rate()
        assert hit_rate == 0.5  # 1 hit, 1 miss
    
    def test_correlation_tracker(self):
        """Test correlation tracking"""
        from src.core.observability import CorrelationTracker
        
        tracker = CorrelationTracker()
        
        # Start request
        correlation_id = tracker.generate_correlation_id()
        tracker.start_request(correlation_id, "test_operation")
        
        # Add events
        tracker.add_event(correlation_id, "cache_hit", {"key": "test"})
        tracker.add_event(correlation_id, "operation_complete")
        
        # End request
        summary = tracker.end_request(correlation_id)
        
        assert summary["operation"] == "test_operation"
        assert len(summary["events"]) == 2
        assert summary["events"][0]["event"] == "cache_hit"
