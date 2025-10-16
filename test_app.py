#!/usr/bin/env python3
"""
App di test per verificare i nuovi endpoint dei resi
"""
from fastapi import FastAPI
from src.routers.order import router as order_router
from src.routers.customer import router as customer_router

# Configura il container
from src.core.container_config import get_configured_container
container = get_configured_container()

app = FastAPI(
    title="ECommerce Manager API - Test Resi",
    description="API per testare la funzionalità dei resi",
    version="1.0.0"
)

# Includi solo i router essenziali
app.include_router(order_router)
app.include_router(customer_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
