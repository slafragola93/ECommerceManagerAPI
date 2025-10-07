from fastapi import FastAPI, HTTPException
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from starlette.middleware.cors import CORSMiddleware

from src.routers import customer, auth, category, brand, shipping_state, product, country, address, carrier, \
    api_carrier, carrier_assignment, platform, shipping, lang, sectional, message, role, configuration, app_configuration, payment, tax, user, \
    order_state, order, invoice, order_package, order_detail, sync, preventivi, fiscal_documents
from src.database import Base, engine

# Import new cache system
from src.core.cache import get_cache_manager, close_cache_manager
from src.middleware.conditional import setup_conditional_middleware
from src.core.settings import get_cache_settings

# Legacy cache (keep for compatibility)
try:
    from fastapi_cache import FastAPICache
    from fastapi_cache.backends.redis import RedisBackend
    from fastapi_cache.decorator import cache
    from redis import asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Initialize new cache system
    try:
        cache_manager = await get_cache_manager()
        settings = get_cache_settings()
        print(f"Cache system initialized: {settings.cache_backend} backend, enabled: {settings.cache_enabled}")
    except Exception as e:
        print(f"WARNING: Cache initialization failed: {e}")
    
    # Initialize legacy cache for compatibility
    if REDIS_AVAILABLE:
        try:
            redis = aioredis.from_url("redis://localhost")
            FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
            print("Legacy Redis cache initialized")
        except Exception as e:
            print(f"WARNING: Legacy Redis connection failed: {e}")
    
    yield
    
    # Cleanup
    try:
        await close_cache_manager()
        print("Cache system closed")
    except Exception as e:
        print(f"WARNING: Cache cleanup failed: {e}")

app = FastAPI(
    title="Elettronew API",
    lifespan=lifespan
)

if REDIS_AVAILABLE:
    @cache()
    async def get_cache():
        return 1
else:
    async def get_cache():
        return 1



origins = ["http://localhost:4200","http://localhost:63297","http://localhost:8000"]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup cache middleware
try:
    setup_conditional_middleware(app, cache_control_ttl=300)
    print("Conditional GET middleware configured")
except Exception as e:
    print(f"WARNING: Cache middleware setup failed: {e}")

app.include_router(auth.router)
app.include_router(user.router)
app.include_router(role.router)
app.include_router(configuration.router)
app.include_router(app_configuration.router)
app.include_router(lang.router)
app.include_router(customer.router)
app.include_router(category.router)
app.include_router(brand.router)
app.include_router(product.router)
app.include_router(shipping_state.router)
app.include_router(country.router)
app.include_router(address.router)
app.include_router(order.router)
app.include_router(carrier.router)
app.include_router(api_carrier.router)
app.include_router(carrier_assignment.router)
app.include_router(platform.router)
app.include_router(sectional.router)
app.include_router(message.router)
app.include_router(payment.router)
app.include_router(tax.router)
app.include_router(order_state.router)
app.include_router(shipping.router)
app.include_router(order_package.router)
app.include_router(order_detail.router)
app.include_router(sync.router)
app.include_router(preventivi.router)
app.include_router(fiscal_documents.router)


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)

# Cache management endpoints
@app.get("/health/cache")
async def cache_health():
    """Cache health check endpoint"""
    try:
        cache_manager = await get_cache_manager()
        stats = await cache_manager.get_stats()
        return {
            "status": "healthy",
            "cache_enabled": stats.get("enabled", False),
            "backend": stats.get("backend", "unknown"),
            "memory_cache": stats.get("memory", {}),
            "redis_cache": stats.get("redis", {}),
            "circuit_breaker": stats.get("circuit_breaker", {})
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Cache unhealthy: {str(e)}")

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    try:
        from src.core.observability import get_metrics
        metrics = get_metrics()
        stats = metrics.get_stats()
        
        # Format for Prometheus
        prometheus_metrics = []
        
        # Cache hit rate
        hit_rate = stats.get("hit_rates", {}).get("overall", 0)
        prometheus_metrics.append(f"cache_hit_rate {hit_rate}")
        
        # Memory cache size
        memory_stats = stats.get("memory", {})
        if memory_stats:
            size = memory_stats.get("size", 0)
            prometheus_metrics.append(f"cache_memory_size {size}")
        
        # Redis stats
        redis_stats = stats.get("redis", {})
        if redis_stats and "connected_clients" in redis_stats:
            clients = redis_stats["connected_clients"]
            prometheus_metrics.append(f"redis_connected_clients {clients}")
        
        return "\n".join(prometheus_metrics)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics error: {str(e)}")

# Admin cache endpoints (require ADMIN role)
@app.delete("/api/v1/cache")
async def clear_cache_pattern(pattern: str = "*"):
    """Clear cache by pattern (Admin only)"""
    # TODO: Add admin authentication check
    try:
        cache_manager = await get_cache_manager()
        deleted = await cache_manager.delete_pattern(pattern)
        return {"message": f"Deleted {deleted} cache keys matching pattern: {pattern}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache clear error: {str(e)}")

@app.post("/api/v1/cache/reset")
async def reset_all_cache():
    """Reset all cache (Admin only - use with caution)"""
    # TODO: Add admin authentication check
    try:
        from src.core.invalidation import invalidate_all_cache
        await invalidate_all_cache()
        return {"message": "All cache cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache reset error: {str(e)}")

@app.get("/api/v1/cache/stats")
async def cache_stats():
    """Get detailed cache statistics (Admin only)"""
    # TODO: Add admin authentication check
    try:
        from src.core.observability import get_metrics
        metrics = get_metrics()
        return metrics.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats error: {str(e)}")

