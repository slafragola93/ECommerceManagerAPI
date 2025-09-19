#!/usr/bin/env python3
"""
Script per pulire il database eliminando tutti i dati.
"""

import sys
import os

# Aggiungi il path del progetto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import SessionLocal, engine
from src.models import *
from sqlalchemy import text

def clear_database():
    """Pulisce il database eliminando tutti i dati."""
    
    db = SessionLocal()
    
    try:
        print("🧹 Inizio pulizia database...")
        
        # Disabilita i controlli di foreign key
        db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        
        # Lista delle tabelle in ordine di dipendenza (dalla più dipendente alla meno dipendente)
        tables = [
            'orders_history',
            'user_roles', 
            'order_details',
            'order_packages',
            'shipments',
            'invoices',
            'orders_document',
            'orders',
            'addresses',
            'customers',
            'users',
            'messages',
            'configurations',
            'taxes',
            'shipping_state',
            'carriers_api',
            'carriers',
            'order_states',
            'sectionals',
            'platforms',
            'products',
            'brands',
            'categories',
            'roles',
            'languages',
            'countries',
            'payments'
        ]
        
        for table in tables:
            try:
                db.execute(text(f"DELETE FROM {table}"))
                print(f"✅ Pulita tabella {table}")
            except Exception as e:
                print(f"⚠️ Errore nella pulizia di {table}: {e}")
        
        # Riabilita i controlli di foreign key
        db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        
        db.commit()
        print("\n🎉 Database pulito con successo!")
        
    except Exception as e:
        print(f"❌ Errore durante la pulizia del database: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    clear_database()
