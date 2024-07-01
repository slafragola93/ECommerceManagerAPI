from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from src.schemas import *
from src.routers import customer, auth, category, brand, shipping_state, product, country, address, carrier, \
    api_carrier, platform, tag, shipping, lang, sectional, message, role, configuration, payment, tax, user, order_state, order, invoice
from src.database import Base, engine

app = FastAPI(
    title="Elettronew API"
)


@app.get("/", tags=["Healthy Check"])
def healthy():
    return {"status": "ok"}


origins = ["http://192.168.130.119:8000", "http://localhost:60530", "http://localhost:4200"]

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
app.include_router(platform.router)
app.include_router(tag.router)
app.include_router(sectional.router)
app.include_router(message.router)
app.include_router(payment.router)
app.include_router(tax.router)
app.include_router(order_state.router)
app.include_router(shipping.router)
app.include_router(invoice.router)


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
