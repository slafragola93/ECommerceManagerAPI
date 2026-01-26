import sys
import asyncio
import logging
import os
import traceback
from datetime import datetime
from pathlib import Path
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

# Fix for Windows file descriptor limit issue
if sys.platform == 'win32':
    loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)
    print("DEBUG: Using ProactorEventLoop for Windows to handle more file descriptors")

from src.routers import customer, auth, category, brand, shipping_state, product, country, address, carrier, \
    api_carrier, carrier_assignment, platform, store, shipping, lang, sectional, message, role, app_configuration, payment, tax, user, \
    order_state, order, order_package, sync, preventivi, fiscal_documents, init, carriers_configuration, shipments, events, csv_import, platform_state_trigger, ddt
from src.database import Base, engine

# Import new cache system
from src.core.cache import get_cache_manager, close_cache_manager
from src.middleware.conditional import setup_conditional_middleware
from src.middleware.error_logging import ErrorLoggingMiddleware, PerformanceLoggingMiddleware, SecurityLoggingMiddleware
from src.core.settings import get_cache_settings
from src.core.container_config import get_configured_container
from src.core.static_files import CachedStaticFiles
from src.core.exceptions import (
    BaseApplicationException,
    ValidationException,
    NotFoundException,
    BusinessRuleException,
    InfrastructureException,
    AuthenticationException,
    AuthorizationException,
    AlreadyExistsError,
    ErrorCode
)
from src.core.pydantic_error_formatter import PydanticErrorFormatter
from src.core.monitoring import get_performance_monitor
from src.events.config import EventConfigLoader
from src.events.config.config_schema import EventConfig
from src.events.core.event_bus import EventBus
from src.events.marketplace import MarketplaceClient
from src.events.plugin_loader import PluginLoader
from src.events.plugin_manager import PluginManager
from src.events.runtime import (
    set_config_loader,
    set_event_bus,
    set_marketplace_client,
    set_plugin_manager,
)

# Legacy cache (keep for compatibility)
try:
    from fastapi_cache import FastAPICache
    from fastapi_cache.backends.redis import RedisBackend
    from fastapi_cache.decorator import cache
    from redis import asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


EVENT_CONFIG_PATH = Path("config/event_handlers.yaml")

# Global task tracker per evitare duplicati
_background_tasks = {
    "order_states_sync": None,
    "tracking_polling": None
}


async def start_background_task(
    task_name: str,
    task_function,
    db_session,
    enabled: bool = True
) -> None:
    """
    Avvia una task in background in modo sicuro.
    
    Args:
        task_name: Nome identificativo della task
        task_function: Funzione async da eseguire
        db_session: Sessione DB da passare alla task
        enabled: Se False, la task non viene avviata
    """
    if not enabled:
        print(f"{task_name} disabled by configuration")
        return
    
    try:
        # Verifica se il task è già in esecuzione
        if _background_tasks[task_name] is None or _background_tasks[task_name].done():
            _background_tasks[task_name] = asyncio.create_task(task_function(db_session))
    except Exception as e:
        print(f"✗ Failed to start {task_name}: {e}")


async def stop_background_task(task_name: str) -> None:
    """
    Ferma una task in background in modo sicuro.
    
    Args:
        task_name: Nome identificativo della task
    """
    task = _background_tasks.get(task_name)
    
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        print(f"✓ {task_name} cancelled")
    
    _background_tasks[task_name] = None


def initialize_event_system() -> None:
    """
    Inizializza il sistema di eventi con configurazione e plugin.
    Centralizza la logica di inizializzazione per migliore manutenibilità.
    """
    try:
        config_loader = EventConfigLoader(EVENT_CONFIG_PATH)
        
        # Carica o crea configurazione di default
        try:
            event_config = config_loader.load()
        except FileNotFoundError:
            event_config = EventConfig(
                plugin_directories=["src/events/plugins", "/opt/custom_plugins"],
                enabled_handlers=[],
                disabled_handlers=[],
                routes={"order_status_changed": {}},
            )
            config_loader.save(event_config)
        
        # Inizializza componenti del sistema eventi
        event_bus = EventBus()
        plugin_loader = PluginLoader(event_config.plugin_directories)
        plugin_manager = PluginManager(event_bus, config_loader, plugin_loader)
        marketplace_client = MarketplaceClient(event_config.marketplace)
        
        # Registra componenti nel runtime globale
        set_event_bus(event_bus)
        set_plugin_manager(plugin_manager)
        set_config_loader(config_loader)
        set_marketplace_client(marketplace_client)
        
        return plugin_manager
        
    except Exception as e:
        print(f"✗ Event system initialization failed: {e}")
        raise


def initialize_cache_system() -> None:
    """Inizializza il sistema di cache (nuovo e legacy)."""
    # New cache system
    try:
        settings = get_cache_settings()
        print(f"✓ Cache system: {settings.cache_backend} backend (enabled: {settings.cache_enabled})")
    except Exception as e:
        print(f"⚠ Cache initialization warning: {e}")
    
    # Legacy Redis cache for compatibility
    if REDIS_AVAILABLE:
        try:
            redis = aioredis.from_url("redis://localhost")
            FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
            print("✓ Legacy Redis cache initialized")
        except Exception as e:
            print(f"⚠ Legacy Redis connection warning: {e}")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """
    Gestisce il ciclo di vita dell'applicazione FastAPI.
    Startup: inizializza cache, eventi e background tasks.
    Shutdown: chiude risorse e cancella tasks.
    """
    # ========== STARTUP ==========
    
    # 1. Inizializza cache
    initialize_cache_system()
    
    # 2. Inizializza event system
    try:
        plugin_manager = initialize_event_system()
        await plugin_manager.initialise()
        print("✓ Event system initialized with all plugins")
    except Exception as e:
        print(f"⚠ Event system warning: {e}")
    
    # 3. Avvia background tasks
    from src.database import SessionLocal
    
    # Task: Order States Sync (ogni ora)
    try:
        from src.services.sync.order_state_sync_service import run_order_states_sync_task
        db = SessionLocal()
        await start_background_task(
            "order_states_sync",
            run_order_states_sync_task,
            db,
            enabled=True
        )
    except Exception as e:
        print(f"⚠ Order states sync warning: {e}")
    
    # Task: Tracking Polling (se abilitato)
    tracking_enabled = os.getenv("TRACKING_POLLING_ENABLED", "true").lower() == "true"
    try:
        from src.services.sync.tracking_polling_service import run_tracking_polling_task
        db = SessionLocal()
        await start_background_task(
            "tracking_polling",
            run_tracking_polling_task,
            db,
            enabled=tracking_enabled
        )
    except Exception as e:
        print(f"⚠ Tracking polling warning: {e}")
    
    print("✅ Startup completed\n")
    
    yield
    
    # ========== SHUTDOWN ==========
    print("\n🛑 Shutting down Elettronew API...")
    
    # Ferma tutte le background tasks
    for task_name in list(_background_tasks.keys()):
        await stop_background_task(task_name)
    
    # Chiudi cache
    try:
        await close_cache_manager()
        print("✓ Cache system closed")
    except Exception as e:
        print(f"⚠ Cache cleanup warning: {e}")
    
    print("✅ Shutdown completed\n")


app = FastAPI(
    title="Elettronew API",
    lifespan=lifespan
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inizializza il container DI
get_configured_container()

if REDIS_AVAILABLE:
    @cache()
    async def get_cache():
        return 1
else:
    async def get_cache():
        return 1


# CORS configuration - più permissiva per sviluppo
origins = [
    "http://localhost:4200",
    "http://localhost:63297", 
    "http://localhost:8000",
    "http://127.0.0.1:4200",
    "http://127.0.0.1:8000",
    "http://0.0.0.0:4200",
    "http://0.0.0.0:8000"
]

# Add CORS middleware - DEVE essere il primo middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Add error logging middleware
app.add_middleware(ErrorLoggingMiddleware, log_requests=True, log_responses=False)
app.add_middleware(PerformanceLoggingMiddleware, slow_request_threshold=1.0)
app.add_middleware(SecurityLoggingMiddleware)

# Setup cache middleware
try:
    setup_conditional_middleware(app, cache_control_ttl=300)
except Exception as e:
    print(f"WARNING: Cache middleware setup failed: {e}")

# ============================================================================
# GLOBAL EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(BaseApplicationException)
async def custom_application_exception_handler(request: Request, exc: BaseApplicationException):
    """Handler per eccezioni custom dell'applicazione"""
    logger.error(f"Application exception: {exc.error_code} - {exc.message}", extra={
        "error_code": exc.error_code,
        "details": exc.details,
        "path": str(request.url),
        "method": request.method
    })
    
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )

@app.exception_handler(ValidationException)
async def validation_exception_handler(request: Request, exc: ValidationException):
    """Handler specifico per errori di validazione"""
    logger.warning(f"Validation error: {exc.message}", extra={
        "error_code": exc.error_code,
        "details": exc.details,
        "path": str(request.url)
    })
    
    return JSONResponse(
        status_code=400,
        content=exc.to_dict()
    )

@app.exception_handler(NotFoundException)
async def not_found_exception_handler(request: Request, exc: NotFoundException):
    """Handler specifico per entità non trovate"""
    logger.info(f"Entity not found: {exc.message}", extra={
        "error_code": exc.error_code,
        "details": exc.details,
        "path": str(request.url)
    })
    
    return JSONResponse(
        status_code=404,
        content=exc.to_dict()
    )

@app.exception_handler(AlreadyExistsError)
async def already_exists_exception_handler(request: Request, exc: AlreadyExistsError):
    """Handler specifico per entità già esistenti"""
    logger.warning(f"Entity already exists: {exc.message}", extra={
        "error_code": exc.error_code,
        "details": exc.details,
        "path": str(request.url)
    })
    
    return JSONResponse(
        status_code=409,
        content=exc.to_dict()
    )

@app.exception_handler(BusinessRuleException)
async def business_rule_exception_handler(request: Request, exc: BusinessRuleException):
    """Handler specifico per violazioni regole business"""
    logger.warning(f"Business rule violation: {exc.message}", extra={
        "error_code": exc.error_code,
        "details": exc.details,
        "path": str(request.url)
    })
    
    return JSONResponse(
        status_code=400,
        content=exc.to_dict()
    )

@app.exception_handler(AuthenticationException)
async def authentication_exception_handler(request: Request, exc: AuthenticationException):
    """Handler specifico per errori di autenticazione"""
    logger.warning(f"Authentication error: {exc.message}", extra={
        "error_code": exc.error_code,
        "details": exc.details,
        "path": str(request.url)
    })
    
    return JSONResponse(
        status_code=401,
        content=exc.to_dict()
    )

@app.exception_handler(AuthorizationException)
async def authorization_exception_handler(request: Request, exc: AuthorizationException):
    """Handler specifico per errori di autorizzazione"""
    logger.warning(f"Authorization error: {exc.message}", extra={
        "error_code": exc.error_code,
        "details": exc.details,
        "path": str(request.url)
    })
    
    return JSONResponse(
        status_code=403,
        content=exc.to_dict()
    )

@app.exception_handler(InfrastructureException)
async def infrastructure_exception_handler(request: Request, exc: InfrastructureException):
    """Handler specifico per errori di infrastruttura"""
    logger.error(f"Infrastructure error: {exc.message}", extra={
        "error_code": exc.error_code,
        "details": exc.details,
        "path": str(request.url)
    })
    
    return JSONResponse(
        status_code=500,
        content=exc.to_dict()
    )

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Handler per errori di validazione FastAPI con formattazione standardizzata"""
    pydantic_errors = exc.errors()
    
    logger.warning(f"Errori di validazione: {pydantic_errors}", extra={
        "path": str(request.url),
        "method": request.method
    })
    
    formatted_error = PydanticErrorFormatter.format(
        pydantic_errors,
        error_code=ErrorCode.VALIDATION_ERROR.value
    )
    
    return JSONResponse(
        status_code=formatted_error["status_code"],
        content=formatted_error
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handler per HTTPException di Starlette"""
    logger.info(f"HTTP exception: {exc.status_code} - {exc.detail}", extra={
        "status_code": exc.status_code,
        "path": str(request.url)
    })
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": "HTTP_ERROR",
            "message": str(exc.detail),
            "details": {},
            "status_code": exc.status_code
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handler generico per errori non gestiti"""
    logger.error(f"Unhandled exception: {str(exc)}", extra={
        "path": str(request.url),
        "method": request.method,
        "traceback": traceback.format_exc()
    })
    
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "Internal server error",
            "details": {},
            "status_code": 500
        }
    )

# ============================================================================
# STATIC FILES MOUNT (must be before routers)
# ============================================================================
try:
    media_path = Path("media")
    if media_path.exists():
        app.mount("/media", CachedStaticFiles(directory="media"), name="media")
        logger.info(f"Media files mounted at /media from directory: {media_path.absolute()}")
    else:
        logger.warning(f"Media directory not found: {media_path.absolute()}")
except Exception as e:
    logger.warning(f"Failed to mount media directory: {str(e)}")

# ============================================================================
# ROUTERS
# ============================================================================

app.include_router(auth.router)
app.include_router(user.router)
app.include_router(role.router)
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
app.include_router(store.router)
app.include_router(sectional.router)
app.include_router(message.router)
app.include_router(payment.router)
app.include_router(tax.router)
app.include_router(order_state.router)
app.include_router(shipping.router)
app.include_router(order_package.router)
app.include_router(sync.router)
app.include_router(preventivi.router)
app.include_router(ddt.router)
app.include_router(fiscal_documents.router)
app.include_router(platform_state_trigger.router)
app.include_router(init.router)
app.include_router(carriers_configuration.router)
app.include_router(shipments.router)
app.include_router(events.router)
app.include_router(csv_import.router)

@app.options("/{full_path:path}")
async def options_handler(request: Request, full_path: str):
    """Handle CORS preflight requests"""
    return JSONResponse(
        content={},
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "86400"
        }
    )

@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)

# ============================================================================
# CACHE & MONITORING ENDPOINTS
# ============================================================================

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
        
        prometheus_metrics = []
        
        hit_rate = stats.get("hit_rates", {}).get("overall", 0)
        prometheus_metrics.append(f"cache_hit_rate {hit_rate}")
        
        memory_stats = stats.get("memory", {})
        if memory_stats:
            size = memory_stats.get("size", 0)
            prometheus_metrics.append(f"cache_memory_size {size}")
        
        redis_stats = stats.get("redis", {})
        if redis_stats and "connected_clients" in redis_stats:
            clients = redis_stats["connected_clients"]
            prometheus_metrics.append(f"redis_connected_clients {clients}")
        
        return "\n".join(prometheus_metrics)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics error: {str(e)}")

@app.delete("/api/v1/cache")
async def clear_cache_pattern(pattern: str = "*"):
    """Clear cache by pattern (Admin only)"""
    try:
        cache_manager = await get_cache_manager()
        deleted = await cache_manager.delete_pattern(pattern)
        return {"message": f"Deleted {deleted} cache keys matching pattern: {pattern}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache clear error: {str(e)}")

@app.post("/api/v1/cache/reset")
async def reset_all_cache():
    """Reset all cache (Admin only - use with caution)"""
    try:
        from src.core.invalidation import invalidate_all_cache
        await invalidate_all_cache()
        return {"message": "All cache cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache reset error: {str(e)}")

@app.get("/api/v1/cache/stats")
async def cache_stats():
    """Get detailed cache statistics (Admin only)"""
    try:
        from src.core.observability import get_metrics
        metrics = get_metrics()
        return metrics.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats error: {str(e)}")

@app.get("/api/v1/monitoring/performance")
async def get_performance_metrics():
    """Ottiene le metriche di performance dell'applicazione"""
    try:
        monitor = get_performance_monitor()
        return monitor.get_performance_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Performance metrics error: {str(e)}")

@app.get("/api/v1/monitoring/errors")
async def get_error_metrics():
    """Ottiene le metriche degli errori"""
    try:
        monitor = get_performance_monitor()
        return monitor.error_tracker.get_error_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error metrics error: {str(e)}")

@app.get("/api/v1/monitoring/health")
async def get_health_status():
    """Health check completo dell'applicazione"""
    try:
        monitor = get_performance_monitor()
        performance = monitor.get_performance_summary()
        
        error_rate = performance.get("error_rate", 0)
        avg_response_time = performance.get("average_response_time", 0)
        
        health_status = "healthy"
        if error_rate > 0.1:
            health_status = "degraded"
        elif avg_response_time > 2.0:
            health_status = "slow"
        
        return {
            "status": health_status,
            "timestamp": datetime.now().isoformat(),
            "performance": performance,
            "checks": {
                "error_rate": error_rate,
                "average_response_time": avg_response_time,
                "active_requests": performance.get("active_requests", 0)
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }