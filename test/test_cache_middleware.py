"""
Tests for cache middleware functionality
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient

from src.middleware.conditional import ConditionalGetMiddleware, CacheControlMiddleware
from src.middleware.conditional import generate_etag_from_data, check_if_none_match


class TestConditionalGetMiddleware:
    """Test conditional GET middleware"""
    
    @pytest.fixture
    def app(self):
        """Create test FastAPI app"""
        app = FastAPI()
        
        @app.get("/api/v1/test")
        async def test_endpoint():
            return {"message": "test", "data": [1, 2, 3]}
        
        @app.get("/api/v1/orders/")
        async def orders_endpoint():
            return {"orders": [{"id": 1}, {"id": 2}]}
        
        @app.get("/api/v1/orders/{order_id}")
        async def order_detail_endpoint(order_id: int):
            return {"id": order_id, "reference": f"ORD{order_id:06d}"}
        
        return app
    
    @pytest.fixture
    def middleware(self):
        """Create middleware instance"""
        return ConditionalGetMiddleware(MagicMock(), cache_control_ttl=300)
    
    def test_is_cacheable_endpoint(self, middleware):
        """Test endpoint cacheability check"""
        # Mock request
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/v1/orders/"
        request.url.query = ""
        request.headers = {"user-agent": "test"}
        
        assert middleware._is_cacheable_endpoint(request) is True
        
        # Test non-cacheable endpoint
        request.url.path = "/api/v1/test"
        assert middleware._is_cacheable_endpoint(request) is False
        
        # Test non-GET request
        request.method = "POST"
        assert middleware._is_cacheable_endpoint(request) is False
    
    def test_path_matches_pattern(self, middleware):
        """Test path pattern matching"""
        # Test exact match
        assert middleware._path_matches_pattern("/api/v1/orders/123", "/api/v1/orders/{order_id}") is True
        
        # Test no match
        assert middleware._path_matches_pattern("/api/v1/customers/123", "/api/v1/orders/{order_id}") is False
        
        # Test invalid pattern
        assert middleware._path_matches_pattern("/api/v1/orders/abc", "/api/v1/orders/{order_id}") is False
    
    def test_generate_etag(self, middleware):
        """Test ETag generation"""
        # Mock request
        request = MagicMock()
        request.url.path = "/api/v1/orders/"
        request.url.query = "page=1&limit=10"
        request.headers = {"user-agent": "test-agent"}
        
        etag = middleware._generate_etag(request)
        
        assert etag is not None
        assert etag.startswith('"')
        assert etag.endswith('"')
        assert len(etag) > 10  # Should be a reasonable hash
    
    def test_generate_etag_with_auth(self, middleware):
        """Test ETag generation with authorization header"""
        request = MagicMock()
        request.url.path = "/api/v1/orders/"
        request.url.query = ""
        request.headers = {
            "user-agent": "test-agent",
            "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MTIzfQ.abc123"
        }
        
        etag = middleware._generate_etag(request)
        
        assert etag is not None
        # Should include user context in ETag
    
    def test_etags_match(self, middleware):
        """Test ETag matching"""
        etag1 = '"abc123"'
        etag2 = '"abc123"'
        etag3 = '"def456"'
        
        assert middleware._etags_match(etag1, etag2) is True
        assert middleware._etags_match(etag1, etag3) is False
    
    @pytest.mark.asyncio
    async def test_dispatch_cache_hit(self, middleware):
        """Test middleware with cache hit (304 response)"""
        # Mock request with If-None-Match
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/v1/orders/"
        request.url.query = ""
        request.headers = {
            "if-none-match": '"abc123"',
            "user-agent": "test"
        }
        
        # Mock call_next
        call_next = MagicMock()
        
        # Mock _generate_etag to return matching ETag
        middleware._generate_etag = MagicMock(return_value='"abc123"')
        
        response = await middleware.dispatch(request, call_next)
        
        # Should return 304 Not Modified
        assert response.status_code == 304
        assert response.headers["etag"] == '"abc123"'
        assert response.headers["cache-control"] == "public, max-age=300"
        
        # Should not call next handler
        call_next.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_dispatch_cache_miss(self, middleware):
        """Test middleware with cache miss"""
        # Mock request without If-None-Match
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/v1/orders/"
        request.url.query = ""
        request.headers = {"user-agent": "test"}
        
        # Mock response
        response = JSONResponse({"orders": [{"id": 1}]})
        
        # Mock call_next
        call_next = MagicMock(return_value=response)
        
        # Mock _generate_etag
        middleware._generate_etag = MagicMock(return_value='"def456"')
        
        result = await middleware.dispatch(request, call_next)
        
        # Should call next handler and add headers
        call_next.assert_called_once_with(request)
        assert result.headers["etag"] == '"def456"'
        assert result.headers["cache-control"] == "public, max-age=300"


class TestCacheControlMiddleware:
    """Test cache control middleware"""
    
    @pytest.fixture
    def middleware(self):
        """Create middleware instance"""
        return CacheControlMiddleware(MagicMock())
    
    @pytest.mark.asyncio
    async def test_dispatch_get_success(self, middleware):
        """Test middleware with successful GET request"""
        request = MagicMock()
        request.method = "GET"
        
        response = JSONResponse({"data": "test"})
        
        call_next = MagicMock(return_value=response)
        
        result = await middleware.dispatch(request, call_next)
        
        # Should add cache headers
        assert "cache-control" in result.headers
        assert "vary" in result.headers
        assert result.headers["cache-control"].startswith("public, max-age=")
    
    @pytest.mark.asyncio
    async def test_dispatch_non_get(self, middleware):
        """Test middleware with non-GET request"""
        request = MagicMock()
        request.method = "POST"
        
        response = JSONResponse({"result": "created"})
        
        call_next = MagicMock(return_value=response)
        
        result = await middleware.dispatch(request, call_next)
        
        # Should add no-cache headers
        assert result.headers["cache-control"] == "no-cache, no-store, must-revalidate"
    
    @pytest.mark.asyncio
    async def test_dispatch_error_response(self, middleware):
        """Test middleware with error response"""
        request = MagicMock()
        request.method = "GET"
        
        response = JSONResponse({"error": "Not found"}, status_code=404)
        
        call_next = MagicMock(return_value=response)
        
        result = await middleware.dispatch(request, call_next)
        
        # Should add no-cache headers for errors
        assert result.headers["cache-control"] == "no-cache, no-store, must-revalidate"


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_generate_etag_from_data(self):
        """Test ETag generation from data"""
        data = {"message": "test", "data": [1, 2, 3]}
        
        etag = generate_etag_from_data(data)
        
        assert etag.startswith('"')
        assert etag.endswith('"')
        assert len(etag) > 10
    
    def test_generate_etag_from_updated_at(self):
        """Test ETag generation from timestamp"""
        timestamp = "2024-01-15T10:30:00Z"
        
        etag = generate_etag_from_updated_at(timestamp)
        
        assert etag.startswith('"')
        assert etag.endswith('"')
        assert len(etag) > 10
    
    def test_check_if_none_match(self):
        """Test If-None-Match header checking"""
        request = MagicMock()
        
        # Test with matching header
        request.headers = {"if-none-match": '"abc123"'}
        assert check_if_none_match(request, '"abc123"') is True
        
        # Test with non-matching header
        request.headers = {"if-none-match": '"def456"'}
        assert check_if_none_match(request, '"abc123"') is False
        
        # Test with multiple ETags
        request.headers = {"if-none-match": '"abc123", "def456"'}
        assert check_if_none_match(request, '"abc123"') is True
        assert check_if_none_match(request, '"def456"') is True
        assert check_if_none_match(request, '"xyz789"') is False
        
        # Test without header
        request.headers = {}
        assert check_if_none_match(request, '"abc123"') is False


class TestMiddlewareIntegration:
    """Test middleware integration with FastAPI app"""
    
    @pytest.fixture
    def app_with_middleware(self):
        """Create app with middleware"""
        app = FastAPI()
        
        # Add middleware
        app.add_middleware(ConditionalGetMiddleware, cache_control_ttl=300)
        app.add_middleware(CacheControlMiddleware)
        
        @app.get("/api/v1/orders/")
        async def orders_endpoint():
            return {"orders": [{"id": 1, "reference": "ORD001"}]}
        
        @app.get("/api/v1/orders/{order_id}")
        async def order_detail_endpoint(order_id: int):
            return {"id": order_id, "reference": f"ORD{order_id:06d}"}
        
        return app
    
    def test_middleware_with_test_client(self, app_with_middleware):
        """Test middleware with FastAPI test client"""
        client = TestClient(app_with_middleware)
        
        # First request
        response = client.get("/api/v1/orders/")
        assert response.status_code == 200
        
        # Should have cache headers
        assert "etag" in response.headers
        assert "cache-control" in response.headers
        assert "vary" in response.headers
        
        etag = response.headers["etag"]
        
        # Second request with If-None-Match
        response = client.get("/api/v1/orders/", headers={"if-none-match": etag})
        assert response.status_code == 304
        
        # Should not have response body for 304
        assert response.content == b''
    
    def test_middleware_with_parameterized_endpoint(self, app_with_middleware):
        """Test middleware with parameterized endpoint"""
        client = TestClient(app_with_middleware)
        
        # Test parameterized endpoint
        response = client.get("/api/v1/orders/123")
        assert response.status_code == 200
        
        assert "etag" in response.headers
        assert response.json()["id"] == 123
        assert response.json()["reference"] == "ORD000123"
