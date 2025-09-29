from fastapi import FastAPI

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


from starlette.middleware.cors import CORSMiddleware

from src.routers import customer, auth, category, brand, shipping_state, product, country, address, carrier, \
    api_carrier, carrier_assignment, platform, shipping, lang, sectional, message, role, configuration, app_configuration, payment, tax, user, \
    order_state, order, invoice, order_package, order_detail, sync, fatturapa, preventivi
from src.database import Base, engine

try:
    from fastapi_cache import FastAPICache
    from fastapi_cache.backends.redis import RedisBackend
    from fastapi_cache.decorator import cache
    from redis import asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("WARNING: Redis not available, cache disabled")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if REDIS_AVAILABLE:
        try:
            redis = aioredis.from_url("redis://localhost")
            FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
            print("Redis cache initialized")
        except Exception as e:
            print(f"WARNING: Redis connection failed: {e}, cache disabled")
    else:
        print("Redis not available, cache disabled")
    yield

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(invoice.router)
app.include_router(order_package.router)
app.include_router(order_detail.router)
app.include_router(sync.router)
app.include_router(fatturapa.router)
app.include_router(preventivi.router)


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)

