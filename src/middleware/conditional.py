"""
ETag and Conditional GET middleware for caching
"""

import hashlib
import json
import logging
from typing import Any, Dict, Optional, Union
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.cache import get_cache_manager
from ..core.settings import get_cache_settings

logger = logging.getLogger(__name__)


class ConditionalGetMiddleware(BaseHTTPMiddleware):
    """
    Middleware for ETag and Conditional GET support
    
    Automatically handles:
    - ETag generation for JSON responses
    - If-None-Match header processing (304 responses)
    - Cache-Control headers
    - Vary header for proper caching
    """
    
    def __init__(self, app: ASGIApp, cache_control_ttl: int = 300):
        super().__init__(app)
        self.settings = get_cache_settings()
        self.cache_control_ttl = cache_control_ttl
        self._cache_manager = None
        
        # Endpoints that should be cached
        self.cacheable_endpoints = {
            "GET /api/v1/addresses/",
            "GET /api/v1/addresses/{address_id}",
            "GET /api/v1/api_carriers/",
            "GET /api/v1/api_carriers/{carrier_api_id}",
            "GET /api/v1/app_configurations/",
            "GET /api/v1/app_configurations/{app_configuration_id}",
            "GET /api/v1/brands/",
            "GET /api/v1/brands/{brand_id}",
            "GET /api/v1/carrier_assignments/",
            "GET /api/v1/carrier_assignments/{assignment_id}",
            "GET /api/v1/carriers/",
            "GET /api/v1/carriers/{carrier_id}",
            "GET /api/v1/categories/",
            "GET /api/v1/categories/{category_id}",
            "GET /api/v1/configurations/",
            "GET /api/v1/configurations/{configuration_id}",
            "GET /api/v1/countries/",
            "GET /api/v1/countries/{country_id}",
            "GET /api/v1/customers/",
            "GET /api/v1/customers/{customer_id}",
            "GET /api/v1/fiscal_documents/",
            "GET /api/v1/fiscal_documents/{id_fiscal_document}",
            "GET /api/v1/languages/",
            "GET /api/v1/languages/{lang_id}",
            "GET /api/v1/messages/",
            "GET /api/v1/messages/{message_id}",
            "GET /api/v1/order_details/",
            "GET /api/v1/order_details/{order_detail_id}",
            "GET /api/v1/order_documents/",
            "GET /api/v1/order_packages/",
            "GET /api/v1/order_packages/{order_package_id}",
            "GET /api/v1/order_states/",
            "GET /api/v1/order_states/{order_state_id}",
            "GET /api/v1/orders/",
            "GET /api/v1/orders/{order_id}",
            "GET /api/v1/payments/",
            "GET /api/v1/payments/{payment_id}",
            "GET /api/v1/platforms/",
            "GET /api/v1/platforms/{platform_id}",
            "GET /api/v1/preventivi/",
            "GET /api/v1/preventivi/{id_order_document}",
            "GET /api/v1/products/",
            "GET /api/v1/products/{product_id}",
            "GET /api/v1/roles/",
            "GET /api/v1/roles/{role_id}",
            "GET /api/v1/sectionals/",
            "GET /api/v1/sectionals/{sectional_id}",
            "GET /api/v1/shipping_states/",
            "GET /api/v1/shipping_states/{shipping_state_id}",
            "GET /api/v1/shippings/",
            "GET /api/v1/shippings/{shipping_id}",
            "GET /api/v1/taxes/",
            "GET /api/v1/taxes/{tax_id}",
            "GET /api/v1/user/",
            "GET /api/v1/user/{user_id}",
        }
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with conditional GET support"""
        
        # Only process GET requests
        if request.method != "GET":
            return await call_next(request)
        
        # Check if endpoint is cacheable
        if not self._is_cacheable_endpoint(request):
            return await call_next(request)
        
        # Initialize cache manager if needed
        if not self._cache_manager:
            self._cache_manager = await get_cache_manager()
        
        # Generate ETag from request
        etag = await self._generate_etag(request)
        if not etag:
            return await call_next(request)
        
        # Check If-None-Match header
        if_none_match = request.headers.get("if-none-match")
        if if_none_match and self._etags_match(etag, if_none_match):
            # Return 304 Not Modified
            response = Response(status_code=304)
            response.headers["etag"] = etag
            response.headers["cache-control"] = f"public, max-age={self.cache_control_ttl}"
            response.headers["vary"] = "Accept, Authorization"
            logger.debug(f"304 Not Modified for {request.url}")
            return response
        
        # Process request normally
        try:
            response = await call_next(request)
            
            # Check if response is None (should not happen, but handle gracefully)
            if response is None:
                logger.error(
                    f"None response returned for {request.method} {request.url.path}",
                    extra={
                        "method": request.method,
                        "path": str(request.url.path)
                    }
                )
                return JSONResponse(
                    status_code=500,
                    content={
                        "error_code": "NO_RESPONSE",
                        "message": "No response returned from route handler",
                        "details": {
                            "path": str(request.url.path),
                            "method": request.method
                        },
                        "status_code": 500
                    }
                )
            
            # Add caching headers to successful responses
            if isinstance(response, JSONResponse) and response.status_code == 200:
                response.headers["etag"] = etag
                response.headers["cache-control"] = f"public, max-age={self.cache_control_ttl}"
                response.headers["vary"] = "Accept, Authorization"
                
                # Add last-modified if available
                last_modified = self._get_last_modified(request)
                if last_modified:
                    response.headers["last-modified"] = last_modified
            
            return response
            
        except (RuntimeError, ValueError, TypeError) as e:
            # Handle "No response returned" and similar errors from call_next
            error_message = str(e).lower()
            if any(keyword in error_message for keyword in ["no response returned", "no response", "response returned", "endofstream"]):
                logger.error(
                    f"No response returned for {request.method} {request.url.path}: {type(e).__name__} - {str(e)}",
                    extra={
                        "method": request.method,
                        "path": str(request.url.path),
                        "error_type": type(e).__name__,
                        "error": str(e)
                    },
                    exc_info=True
                )
                # Return a proper error response instead of letting the exception propagate
                return JSONResponse(
                    status_code=500,
                    content={
                        "error_code": "NO_RESPONSE",
                        "message": "No response returned from route handler",
                        "details": {
                            "path": str(request.url.path),
                            "method": request.method,
                            "error_type": type(e).__name__
                        },
                        "status_code": 500
                    }
                )
            # Re-raise other exceptions of these types
            raise
        except Exception as e:
            # Re-raise other exceptions to be handled by exception handlers
            raise
    
    def _is_cacheable_endpoint(self, request: Request) -> bool:
        """Check if endpoint should be cached"""
        
        # Check exact match
        path = str(request.url.path)
        method = request.method
        
        endpoint_key = f"{method} {path}"
        if endpoint_key in self.cacheable_endpoints:
            return True
        
        # Check pattern match for parameterized endpoints
        for cacheable_pattern in self.cacheable_endpoints:
            if self._path_matches_pattern(path, cacheable_pattern):
                return True
        
        return False
    
    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches cacheable pattern"""
        import re
        
        # Convert FastAPI path pattern to regex
        # /api/v1/orders/{order_id} -> /api/v1/orders/\d+
        pattern_regex = pattern.replace("{", "(?P<").replace("}", ">\\d+)")
        pattern_regex = f"^{pattern_regex}$"
        
        return bool(re.match(pattern_regex, path))
    
    async def _generate_etag(self, request: Request) -> Optional[str]:
        """Generate ETag for request"""
        try:
            # Create ETag from URL and query parameters
            etag_data = {
                "path": str(request.url.path),
                "query": str(request.url.query),
                "user_agent": request.headers.get("user-agent", ""),
            }
            
            # Add user context if available (for user-specific caching)
            auth_header = request.headers.get("authorization")
            if auth_header:
                # Extract user ID from JWT token (simplified)
                try:
                    user_id = self._extract_user_id_from_token(auth_header)
                    if user_id:
                        etag_data["user_id"] = user_id
                except Exception:
                    pass  # Ignore token parsing errors
            
            # Generate hash
            etag_string = json.dumps(etag_data, sort_keys=True)
            etag_hash = hashlib.md5(etag_string.encode()).hexdigest()
            
            return f'"{etag_hash}"'
            
        except Exception as e:
            logger.error(f"ETag generation error: {e}")
            return None
    
    def _extract_user_id_from_token(self, auth_header: str) -> Optional[str]:
        """Extract user ID from JWT token (simplified implementation)"""
        try:
            # Remove "Bearer " prefix
            token = auth_header.replace("Bearer ", "")
            
            # Decode JWT payload (without verification for ETag purposes)
            import base64
            import json
            
            # Split token and get payload
            parts = token.split(".")
            if len(parts) != 3:
                return None
            
            # Decode payload (add padding if needed)
            payload = parts[1]
            payload += "=" * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            payload_data = json.loads(decoded)
            
            return str(payload_data.get("id", ""))
            
        except Exception:
            return None
    
    def _etags_match(self, etag1: str, etag2: str) -> bool:
        """Check if two ETags match"""
        # Remove quotes and compare
        etag1_clean = etag1.strip('"')
        etag2_clean = etag2.strip('"')
        
        return etag1_clean == etag2_clean
    
    def _get_last_modified(self, request: Request) -> Optional[str]:
        """Get Last-Modified header value"""
        # This could be enhanced to check actual resource modification time
        # For now, return None to let the application handle it
        return None


class CacheControlMiddleware(BaseHTTPMiddleware):
    """
    Middleware for adding Cache-Control headers to responses
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.settings = get_cache_settings()
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Add cache control headers"""
        
        try:
            response = await call_next(request)
            
            if response is None:
                return JSONResponse(
                    status_code=500,
                    content={
                        "error_code": "NO_RESPONSE",
                        "message": "No response returned from route handler",
                        "details": {
                            "path": str(request.url.path),
                            "method": request.method
                        },
                        "status_code": 500
                    }
                )
            
            # Add default cache headers for successful GET requests
            if (request.method == "GET" and 
                response.status_code == 200 and 
                isinstance(response, JSONResponse)):
                
                # Check if Cache-Control is already set
                if "cache-control" not in response.headers:
                    response.headers["cache-control"] = f"public, max-age={self.settings.cache_default_ttl}"
                
                # Add Vary header for proper caching
                if "vary" not in response.headers:
                    response.headers["vary"] = "Accept, Authorization"
            
            # Add no-cache headers for non-GET requests and error responses
            elif (request.method != "GET" or 
                  response.status_code >= 400):
                
                if "cache-control" not in response.headers:
                    response.headers["cache-control"] = "no-cache, no-store, must-revalidate"
            
            return response
            
        except (RuntimeError, ValueError, TypeError) as exc:
            # Handle "No response returned" and similar errors from call_next
            error_message = str(exc).lower()
            if any(keyword in error_message for keyword in ["no response returned", "no response", "response returned", "endofstream"]):
                logger.error(
                    f"No response returned for {request.method} {request.url.path}: {type(exc).__name__} - {str(exc)}",
                    extra={
                        "method": request.method,
                        "path": str(request.url.path),
                        "error_type": type(exc).__name__,
                        "error": str(exc)
                    },
                    exc_info=True
                )
                # Return a proper error response instead of letting the exception propagate
                return JSONResponse(
                    status_code=500,
                    content={
                        "error_code": "NO_RESPONSE",
                        "message": "No response returned from route handler",
                        "details": {
                            "path": str(request.url.path),
                            "method": request.method,
                            "error_type": type(exc).__name__
                        },
                        "status_code": 500
                    }
                )
            # Re-raise other exceptions of these types
            raise
        except Exception as exc:
            # Re-raise other exceptions to be handled by exception handlers
            raise


def setup_conditional_middleware(app, cache_control_ttl: int = 300):
    """Setup conditional GET middleware for FastAPI app"""
    
    # Add conditional GET middleware
    app.add_middleware(
        ConditionalGetMiddleware,
        cache_control_ttl=cache_control_ttl
    )
    
    # Add cache control middleware
    app.add_middleware(CacheControlMiddleware)
    
    logger.info("Conditional GET middleware configured")


# Utility functions for manual ETag handling

def generate_etag_from_data(data: Any) -> str:
    """Generate ETag from data content"""
    try:
        # Serialize data to JSON
        if isinstance(data, (dict, list)):
            json_str = json.dumps(data, sort_keys=True, default=str)
        else:
            json_str = str(data)
        
        # Generate hash
        etag_hash = hashlib.md5(json_str.encode()).hexdigest()
        return f'"{etag_hash}"'
        
    except Exception as e:
        logger.error(f"ETag generation error: {e}")
        return f'"{hash(str(data))}"'


def generate_etag_from_updated_at(updated_at: str) -> str:
    """Generate ETag from updated_at timestamp"""
    try:
        etag_hash = hashlib.md5(updated_at.encode()).hexdigest()
        return f'"{etag_hash}"'
    except Exception:
        return f'"{hash(updated_at)}"'


def check_if_none_match(request: Request, etag: str) -> bool:
    """Check if request has matching If-None-Match header"""
    if_none_match = request.headers.get("if-none-match")
    if not if_none_match:
        return False
    
    # Handle multiple ETags in If-None-Match
    if_none_match_etags = [e.strip().strip('"') for e in if_none_match.split(",")]
    etag_clean = etag.strip('"')
    
    return etag_clean in if_none_match_etags


def create_not_modified_response(etag: str, cache_control_ttl: int = 300) -> Response:
    """Create 304 Not Modified response"""
    response = Response(status_code=304)
    response.headers["etag"] = etag
    response.headers["cache-control"] = f"public, max-age={cache_control_ttl}"
    response.headers["vary"] = "Accept, Authorization"
    return response
