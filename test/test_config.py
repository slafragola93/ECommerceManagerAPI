"""
Configurazione per i test degli endpoint Order
"""

import os
import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from src.database import *
from test.utils import engine, TestingSessionLocal

# Configurazione ambiente di test
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["MAX_LIMIT"] = "1000"
os.environ["LIMIT_DEFAULT"] = "10"

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Setup del database di test per tutti i test"""
    # Crea tutte le tabelle
    Base.metadata.create_all(bind=engine)
    
    yield
    
    # Cleanup dopo tutti i test
    with engine.connect() as conn:
        # Pulisce tutte le tabelle in ordine corretto (rispettando le foreign key)
        tables_to_clean = [
            "order_details",
            "order_packages", 
            "orders",
            "invoices",
            "addresses",
            "customers",
            "users",
            "products",
            "categories",
            "brands",
            "carriers_api",
            "carriers",
            "platforms",
            "languages",
            "sectionals",
            "messages",
            "configurations",
            "payments",
            "order_states",
            "shipments",
            "taxes",
            "shipping_state",
            "countries",
            "roles"
        ]
        
        for table in tables_to_clean:
            try:
                conn.execute(text(f"DELETE FROM {table};"))
            except Exception:
                pass  # Ignora errori se la tabella non esiste
        
        conn.commit()

@pytest.fixture(autouse=True)
def clean_database():
    """Pulisce il database prima di ogni test"""
    with engine.connect() as conn:
        # Pulisce le tabelle principali per ogni test
        tables_to_clean = [
            "order_details",
            "order_packages",
            "orders"
        ]
        
        for table in tables_to_clean:
            try:
                conn.execute(text(f"DELETE FROM {table};"))
            except Exception:
                pass
        
        conn.commit()
    
    yield
    
    # Cleanup dopo ogni test
    with engine.connect() as conn:
        for table in tables_to_clean:
            try:
                conn.execute(text(f"DELETE FROM {table};"))
            except Exception:
                pass
        
        conn.commit()
