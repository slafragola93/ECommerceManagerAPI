"""
Integration tests for cache system with repositories and services
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

from src.repository.cached_order_repository import CachedOrderRepository
from src.repository.cached_lookup_repositories import CachedOrderStateRepository
from src.services.cached_prestashop_service import CachedPrestaShopService
from src.core.invalidation import CacheInvalidationManager
from src.core.cached import cached


class TestCachedOrderRepository:
    """Test cached order repository integration"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock SQLAlchemy session"""
        session = MagicMock(spec=Session)
        session.commit = MagicMock()
        session.add = MagicMock()
        session.refresh = MagicMock()
        return session
    
    @pytest.fixture
    def cached_order_repo(self, mock_session):
        """Create cached order repository"""
        return CachedOrderRepository(mock_session)
    
    @pytest.mark.asyncio
    async def test_get_all_cached(self, cached_order_repo):
        """Test cached get_all functionality"""
        with patch.object(cached_order_repo, 'get_all') as mock_get_all:
            mock_get_all.return_value = [{"id": 1, "reference": "ORD001"}]
            
            # Mock the cache decorator
            with patch('src.core.cached.cached') as mock_cached:
                mock_cached.return_value = lambda func: func
                
                result = await cached_order_repo.get_all_cached("tenant1", qhash="abc123")
                
                assert result == [{"id": 1, "reference": "ORD001"}]
                mock_get_all.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_by_id_cached(self, cached_order_repo):
        """Test cached get_by_id functionality"""
        with patch.object(cached_order_repo, 'get_by_id') as mock_get_by_id:
            mock_get_by_id.return_value = {"id": 1, "reference": "ORD001"}
            
            with patch('src.core.cached.cached') as mock_cached:
                mock_cached.return_value = lambda func: func
                
                result = await cached_order_repo.get_by_id_cached("tenant1", 1)
                
                assert result == {"id": 1, "reference": "ORD001"}
                mock_get_by_id.assert_called_once_with(1)
    
    @pytest.mark.asyncio
    async def test_create_with_cache_invalidation(self, cached_order_repo, mock_session):
        """Test create with cache invalidation"""
        from src.schemas.order_schema import OrderSchema
        
        order_data = OrderSchema(
            id_origin=0,
            customer=1,
            address_delivery=1,
            address_invoice=1,
            reference="ORD001",
            id_platform=1,
            id_payment=1,
            shipping=1,
            sectional=1,
            id_order_state=1,
            is_invoice_requested=False,
            is_payed=0,
            payment_date=None,
            total_weight=1.0,
            total_price=100.0,
            total_discounts=0.0,
            cash_on_delivery=0.0
        )
        
        with patch.object(cached_order_repo, 'create') as mock_create:
            mock_create.return_value = 123
            
            with patch('src.core.cached.CacheContext') as mock_context:
                mock_ctx = AsyncMock()
                mock_context.return_value.__aenter__.return_value = mock_ctx
                mock_context.return_value.__aexit__.return_value = None
                
                result = await cached_order_repo.create_with_cache_invalidation(order_data, "tenant1")
                
                assert result == 123
                mock_create.assert_called_once_with(order_data)
                mock_ctx.invalidate.assert_called()


class TestCachedLookupRepositories:
    """Test cached lookup repositories"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock SQLAlchemy session"""
        return MagicMock(spec=Session)
    
    @pytest.fixture
    def cached_order_state_repo(self, mock_session):
        """Create cached order state repository"""
        return CachedOrderStateRepository(mock_session)
    
    @pytest.mark.asyncio
    async def test_get_all_cached_lookup(self, cached_order_state_repo):
        """Test cached lookup get_all"""
        with patch.object(cached_order_state_repo, 'get_all') as mock_get_all:
            mock_get_all.return_value = [
                {"id": 1, "name": "Pending"},
                {"id": 2, "name": "Processing"}
            ]
            
            with patch('src.core.cached.cached') as mock_cached:
                mock_cached.return_value = lambda func: func
                
                result = await cached_order_state_repo.get_all_cached("tenant1")
                
                assert len(result) == 2
                assert result[0]["name"] == "Pending"
                mock_get_all.assert_called_once()
    
    def test_get_all_with_cache_disabled(self, cached_order_state_repo):
        """Test get_all when cache is disabled"""
        cached_order_state_repo.settings.cache_enabled = False
        
        with patch.object(cached_order_state_repo, 'get_all') as mock_get_all:
            mock_get_all.return_value = [{"id": 1, "name": "Pending"}]
            
            result = cached_order_state_repo.get_all_with_cache("tenant1")
            
            assert result == [{"id": 1, "name": "Pending"}]
            mock_get_all.assert_called_once()


class TestCachedPrestaShopService:
    """Test cached PrestaShop service"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return MagicMock(spec=Session)
    
    @pytest.fixture
    def cached_prestashop_service(self, mock_db):
        """Create cached PrestaShop service"""
        return CachedPrestaShopService(mock_db, platform_id=1)
    
    @pytest.mark.asyncio
    async def test_get_orders_cached(self, cached_prestashop_service):
        """Test cached PrestaShop orders fetch"""
        with patch('src.core.cached.cached') as mock_cached:
            mock_cached.return_value = lambda func: func
            
            result = await cached_prestashop_service.get_orders_cached(
                "tenant1", "shop123", page=1
            )
            
            assert result["cached"] is True
            assert result["page"] == 1
            assert "orders" in result
    
    @pytest.mark.asyncio
    async def test_sync_orders_with_cache(self, cached_prestashop_service):
        """Test sync orders with cache invalidation"""
        cached_prestashop_service.settings.cache_external_apis_enabled = True
        
        with patch.object(cached_prestashop_service, 'get_orders_cached') as mock_get_cached:
            mock_get_cached.return_value = {
                "orders": [{"id": 1, "reference": "PS001"}],
                "cached": True
            }
            
            with patch.object(cached_prestashop_service, '_invalidate_sync_caches') as mock_invalidate:
                mock_invalidate.return_value = None
                
                result = await cached_prestashop_service.sync_orders_with_cache(
                    "tenant1", "shop123"
                )
                
                assert len(result) == 1
                assert result[0]["reference"] == "PS001"
                mock_invalidate.assert_called_once()


class TestCacheInvalidationManager:
    """Test cache invalidation manager"""
    
    @pytest.fixture
    def invalidation_manager(self):
        """Create invalidation manager"""
        return CacheInvalidationManager()
    
    @pytest.fixture
    def mock_session(self):
        """Mock SQLAlchemy session"""
        session = MagicMock(spec=Session)
        session.commit = MagicMock()
        return session
    
    def test_add_pending_invalidation(self, invalidation_manager, mock_session):
        """Test adding pending invalidations"""
        invalidation_manager.add_pending_invalidation(mock_session, "test:pattern")
        
        session_id = id(mock_session)
        assert session_id in invalidation_manager._pending_invalidations
        assert "test:pattern" in invalidation_manager._pending_invalidations[session_id]
    
    def test_add_pending_invalidations(self, invalidation_manager, mock_session):
        """Test adding multiple pending invalidations"""
        patterns = ["pattern1", "pattern2", "pattern3"]
        invalidation_manager.add_pending_invalidations(mock_session, patterns)
        
        session_id = id(mock_session)
        assert len(invalidation_manager._pending_invalidations[session_id]) == 3
    
    @pytest.mark.asyncio
    async def test_invalidation_context(self, invalidation_manager, mock_session):
        """Test invalidation context manager"""
        patterns = ["pattern1", "pattern2"]
        
        async with invalidation_manager.invalidation_context(mock_session, patterns) as ctx:
            assert ctx is invalidation_manager
        
        # Check that patterns were added
        session_id = id(mock_session)
        assert session_id in invalidation_manager._pending_invalidations
        assert len(invalidation_manager._pending_invalidations[session_id]) == 2


class TestInvalidationPatterns:
    """Test invalidation pattern utilities"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock SQLAlchemy session"""
        return MagicMock(spec=Session)
    
    def test_invalidate_on_create(self, mock_session):
        """Test create invalidation patterns"""
        from src.core.invalidation import invalidate_on_create
        
        with patch('src.core.invalidation.get_invalidation_manager') as mock_manager:
            manager = MagicMock()
            mock_manager.return_value = manager
            
            invalidate_on_create(mock_session, "order", "tenant1")
            
            manager.add_pending_invalidations.assert_called_once()
            patterns = manager.add_pending_invalidations.call_args[0][1]
            assert "orders:list:tenant1:*" in patterns
            assert "orders:count:tenant1:*" in patterns
    
    def test_invalidate_on_update(self, mock_session):
        """Test update invalidation patterns"""
        from src.core.invalidation import invalidate_on_update
        
        with patch('src.core.invalidation.get_invalidation_manager') as mock_manager:
            manager = MagicMock()
            mock_manager.return_value = manager
            
            invalidate_on_update(mock_session, "order", 123, "tenant1")
            
            manager.add_pending_invalidations.assert_called_once()
            patterns = manager.add_pending_invalidations.call_args[0][1]
            assert "order:tenant1:*:123" in patterns
            assert "orders:list:tenant1:*" in patterns
    
    def test_invalidate_order_related(self, mock_session):
        """Test order-related invalidation patterns"""
        from src.core.invalidation import invalidate_order_related
        
        with patch('src.core.invalidation.get_invalidation_manager') as mock_manager:
            manager = MagicMock()
            mock_manager.return_value = manager
            
            invalidate_order_related(mock_session, 123, "tenant1")
            
            manager.add_pending_invalidations.assert_called_once()
            patterns = manager.add_pending_invalidations.call_args[0][1]
            assert "order:tenant1:*:123" in patterns
            assert "orders:list:tenant1:*" in patterns
            assert "orders:history:tenant1:*:123" in patterns


class TestCacheDecoratorIntegration:
    """Test cache decorator integration with real scenarios"""
    
    @pytest.mark.asyncio
    async def test_cached_with_real_data(self):
        """Test cached decorator with realistic data"""
        
        # Mock cache manager
        with patch('src.core.cached.get_cache_manager') as mock_get_manager:
            cache_manager = AsyncMock()
            cache_manager.get.return_value = None  # Cache miss
            cache_manager.set.return_value = True
            mock_get_manager.return_value = cache_manager
            
            # Test function with realistic order data
            @cached(ttl=300, key="order:{tenant}:{order_id}")
            async def get_order_details(order_id: int, tenant: str):
                return {
                    "id_order": order_id,
                    "reference": f"ORD{order_id:06d}",
                    "customer": {"id": 1, "name": "Test Customer"},
                    "order_details": [
                        {"product_name": "Test Product", "quantity": 2, "price": 50.0}
                    ],
                    "total_price": 100.0,
                    "date_add": "2024-01-15T10:30:00Z"
                }
            
            result = await get_order_details(123, "tenant1")
            
            assert result["id_order"] == 123
            assert result["reference"] == "ORD000123"
            assert len(result["order_details"]) == 1
            
            # Verify cache operations
            cache_manager.get.assert_called_once()
            cache_manager.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cached_with_tenant_extraction(self):
        """Test cached decorator with automatic tenant extraction"""
        
        with patch('src.core.cached.get_cache_manager') as mock_get_manager:
            cache_manager = AsyncMock()
            cache_manager.get.return_value = None
            cache_manager.set.return_value = True
            mock_get_manager.return_value = cache_manager
            
            @cached(ttl=300, key="orders:list:{tenant}:{qhash}", tenant_from_user=True)
            async def get_orders_list(user: dict, filters: dict):
                return {
                    "orders": [{"id": 1}, {"id": 2}],
                    "total": 2,
                    "page": 1
                }
            
            user = {"id": 456, "username": "testuser"}
            filters = {"status": "pending", "page": 1}
            
            result = await get_orders_list(user=user, filters=filters)
            
            assert len(result["orders"]) == 2
            assert result["total"] == 2
            
            # Verify cache key includes tenant
            cache_key = cache_manager.set.call_args[0][0]
            assert "user_456" in cache_key
